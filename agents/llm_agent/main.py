# agents/llm_agent/main.py

import os
import time
import threading
import asyncio
from uuid import uuid4
from datetime import datetime, timezone
from typing import Optional
import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from server.a2a_models import A2AMessage, AgentInfo
from utils.model_utils import generar_sql, generar_respuesta

app = FastAPI(title="LLM Agent (A2A)")

# —————————————————————————————————————————————————————————————————————————————
# CONFIGURACIÓN DESDE ENTORNO
# —————————————————————————————————————————————————————————————————————————————
MCP_URL        = os.getenv("MCP_URL",        "http://mcp-server:8000")
VENTAS_AGENT   = os.getenv("VENTAS_AGENT_ID")
CALLBACK_URL   = os.getenv("CALLBACK_URL",   "http://llm-agent:8003/inbox")
FIXED_AGENT_ID = os.getenv("LLM_AGENT_ID")

if not VENTAS_AGENT:
    raise RuntimeError("Debes definir VENTAS_AGENT_ID en el .env antes de arrancar")

print(f"[LLM Agent] Config → MCP_URL={MCP_URL}  VENTAS_AGENT_ID={VENTAS_AGENT}", flush=True)

agent_id: Optional[str] = None
pending: dict[str, asyncio.Future] = {}

# —————————————————————————————————————————————————————————————————————————————
# ENDPOINT DE DIAGNÓSTICO
# —————————————————————————————————————————————————————————————————————————————
@app.get("/ping")
def ping():
    print("[LLM Agent] /ping recibido", flush=True)
    return {"pong": True}

# —————————————————————————————————————————————————————————————————————————————
# HILO DE REGISTRO A2A
# —————————————————————————————————————————————————————————————————————————————
def register_loop():
    global agent_id
    print("[LLM Agent] register_loop: iniciando…", flush=True)

    payload = AgentInfo(
        name="llm_agent",
        callback_url=CALLBACK_URL,
        capabilities={"role": "sql_to_text"},
        agent_id=FIXED_AGENT_ID
    ).model_dump(exclude_none=True)
    payload["callback_url"] = str(payload["callback_url"])

    print(f"[LLM Agent] payload registro: {payload}", flush=True)
    time.sleep(5)

    for i in range(5):
        try:
            resp = requests.post(f"{MCP_URL}/agent/register", json=payload, timeout=3)
            resp.raise_for_status()
            agent_id = resp.json()["agent_id"]
            print(f"[LLM Agent] registrado con id={agent_id}", flush=True)
            return
        except Exception as e:
            wait = 2 ** i
            print(f"[LLM Agent] intento {i+1} fallo ({e}), retry en {wait}s", flush=True)
            time.sleep(wait)

    print("[LLM Agent] ERROR: no pudo registrarse tras varios intentos", flush=True)

@app.on_event("startup")
def on_startup():
    threading.Thread(target=register_loop, daemon=True).start()

# —————————————————————————————————————————————————————————————————————————————
# ESQUEMA DE PETICIÓN
# —————————————————————————————————————————————————————————————————————————————
class ConsultaRequest(BaseModel):
    pregunta: str

@app.post("/query")
async def hacer_consulta(request: Request):
    # Validación manual para personalizar el error
    try:
        body = await request.json()
        req = ConsultaRequest(**body)
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": "JSON inválido. Debe ser {'pregunta':'...'}"}
        )

    if agent_id is None:
        raise HTTPException(503, "Aún no registrado en MCP; inténtalo de nuevo en unos segundos.")

    print(f"[LLM Agent] /query recibida: {req.pregunta}", flush=True)

    loop = asyncio.get_running_loop()

    # 1) Generar SQL en executor para no bloquear el loop
    print("[LLM Agent] empezando generar_sql…", flush=True)
    sql = await loop.run_in_executor(None, generar_sql, req.pregunta)
    print(f"[LLM Agent] SQL generado: {sql}", flush=True)

    # 2) Preparar mensaje A2A
    corr = uuid4().hex
    msg = A2AMessage(
        message_id=corr,
        sender=agent_id,
        recipient=VENTAS_AGENT,
        timestamp=datetime.now(timezone.utc).isoformat(),
        type="query",
        body={"sql": sql, "correlation_id": corr}
    )

    # 3) Enviar al broker y esperar respuesta
    fut = loop.create_future()
    pending[corr] = fut

    try:
        print(f"[LLM Agent] Enviando mensaje A2A a {VENTAS_AGENT}", flush=True)
        r = requests.post(f"{MCP_URL}/agent/send", json=msg.model_dump(), timeout=5)
        r.raise_for_status()
    except Exception as e:
        pending.pop(corr, None)
        raise HTTPException(502, f"Error enviando A2A: {e}")

    try:
        datos = await asyncio.wait_for(fut, timeout=30)
    except asyncio.TimeoutError:
        pending.pop(corr, None)
        raise HTTPException(504, "Timeout esperando respuesta de ventas-agent")

    # 4) Generar texto final en executor
    print("[LLM Agent] empezando generar_respuesta…", flush=True)
    respuesta = await loop.run_in_executor(None, generar_respuesta, req.pregunta, datos)
    print("[LLM Agent] terminado generar_respuesta", flush=True)

    pending.pop(corr, None)
    print("[LLM Agent] respuesta final lista", flush=True)

    return {"sql": sql, "respuesta": respuesta}

# —————————————————————————————————————————————————————————————————————————————
@app.post("/inbox")
async def inbox(msg: A2AMessage):
    print(f"[LLM Agent] /inbox mensaje: {msg.type}", flush=True)
    print(f"[LLM Agent] inbox recibido con correlation_id={msg.body.get('correlation_id')} (pending: {list(pending.keys())})", flush=True)

    if msg.type == "response" and "correlation_id" in msg.body:
        corr = msg.body["correlation_id"]
        fut = pending.get(corr)
        if fut and not fut.done():
            fut.set_result(msg.body.get("resultado", []))
            return {"status": "ok"}
    return {"status": "ignored"}

# agents/llm_agent/main.py

import os
import time
import threading
import asyncio
from uuid import uuid4
from datetime import datetime, timezone
from typing import Optional, Any, Dict

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from server.a2a_models import A2AMessage, AgentInfo, Envelope
from utils.model_utils import generar_sql, generar_respuesta

app = FastAPI(title="LLM Agent (A2A)")

# —————————————————————————————————————————————————————————————————————————————
# CONFIGURACIÓN DESDE ENTORNO
# —————————————————————————————————————————————————————————————————————————————
MCP_URL        = os.getenv("MCP_URL",      "http://mcp-server:8000")
VENTAS_AGENT   = os.getenv("VENTAS_AGENT_ID")
CALLBACK_URL   = os.getenv("CALLBACK_URL", "http://llm-agent:8003/inbox")
FIXED_AGENT_ID = os.getenv("LLM_AGENT_ID")

if not VENTAS_AGENT:
    raise RuntimeError("Debes definir VENTAS_AGENT_ID en el .env antes de arrancar")

print(f"[LLM Agent] Config → MCP_URL={MCP_URL}  VENTAS_AGENT_ID={VENTAS_AGENT}", flush=True)

agent_id: Optional[str] = None
pending: Dict[str, asyncio.Future] = {}

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
    raise RuntimeError("No pudo registrarse en MCP tras varios intentos")

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
    # 1) Parsear y validar JSON
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

    # 2) Generar SQL en executor
    print("[LLM Agent] empezando generar_sql…", flush=True)
    sql: str = await loop.run_in_executor(None, generar_sql, req.pregunta)
    print(f"[LLM Agent] SQL generado: {sql}", flush=True)

    # 3) Construir mensaje A2A
    corr = uuid4().hex
    msg = A2AMessage(
        message_id=corr,
        sender=agent_id,
        recipient=VENTAS_AGENT,
        timestamp=datetime.now(timezone.utc).isoformat(),
        type="query",
        body={"sql": sql, "correlation_id": corr}
    )

    # 4) Envolver en Envelope y enviar al broker
    env = Envelope(
        version="1.0",
        message_id=msg.message_id,
        timestamp=datetime.now(timezone.utc),
        type=msg.type,
        sender=msg.sender,
        recipient=msg.recipient,
        payload=msg.model_dump()
    )

    pending[corr] = loop.create_future()
    print(f"[LLM Agent] Enviando envelope A2A a {VENTAS_AGENT}", flush=True)

    # Serializar el Envelope a dict, y asegurarnos de que timestamp sea ISO
    envelope_dict = env.model_dump()
    envelope_dict["timestamp"] = env.timestamp.isoformat()

    # Función síncrona que envía el dict
    def send_env_payload(payload: Dict[str, Any]):
        r = requests.post(f"{MCP_URL}/agent/send", json=payload, timeout=5)
        r.raise_for_status()

    # llamada HTTP en executor para no bloquear el event loop
    await loop.run_in_executor(None, send_env_payload, envelope_dict)

    # 5) Esperar respuesta de ventas-agent
    try:
        datos = await asyncio.wait_for(pending[corr], timeout=30)
    except asyncio.TimeoutError:
        pending.pop(corr, None)
        raise HTTPException(504, "Timeout esperando respuesta de ventas-agent")

    # 6) Generar respuesta en executor
    print("[LLM Agent] empezando generar_respuesta…", flush=True)
    respuesta: str = await loop.run_in_executor(None, generar_respuesta, req.pregunta, datos)
    print("[LLM Agent] terminado generar_respuesta", flush=True)

    pending.pop(corr, None)
    print("[LLM Agent] respuesta final lista", flush=True)
    return {"sql": sql, "respuesta": respuesta}

# —————————————————————————————————————————————————————————————————————————————
@app.post("/inbox")
async def inbox(env: Envelope):
    # 1) desplegar envelope
    print(f"[LLM Agent] /inbox envelope tipo={env.type}", flush=True)
    msg = A2AMessage.model_validate(env.payload)

    corr = msg.body.get("correlation_id")
    print(f"[LLM Agent] inbox recibido correlation_id={corr} (pending={list(pending.keys())})", flush=True)
    if msg.type == "response" and corr in pending:
        fut = pending[corr]
        if not fut.done():
            fut.set_result(msg.body.get("resultado", []))
            return {"status": "ok"}
    return {"status": "ignored"}

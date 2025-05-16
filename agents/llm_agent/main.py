# agents/llm_agent/main.py

import os
import time
import threading
import asyncio
from uuid import uuid4
from datetime import datetime, timezone
from typing import Optional, Any, Dict
import logging

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from server.a2a_models import A2AMessage, AgentInfo, Envelope
from utils.model_utils import generar_sql, generar_respuesta

app = FastAPI(title="LLM Agent (A2A)")
logger = logging.getLogger("uvicorn.error")

# —————————————————————————————————————————————————————————————————————————————
# CONFIGURACIÓN DESDE ENTORNO
# —————————————————————————————————————————————————————————————————————————————
# URL base del MCP (service name en Docker Compose)
MCP_URL        = os.getenv("MCP_URL",      "http://mcp-server:8000")
# URL de callback del agente
CALLBACK_URL   = os.getenv("CALLBACK_URL", "http://llm-agent:8003/inbox")
# ID fijo para este agente, leído de .env
FIXED_AGENT_ID = os.getenv("LLM_AGENT_ID")
# Intervalo de heartbeat en segundos
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "30"))

agent_id: Optional[str] = None
pending: Dict[str, asyncio.Future] = {}

# —————————————————————————————————————————————————————————————————————————————
# ENDPOINT DE DIAGNÓSTICO
# —————————————————————————————————————————————————————————————————————————————
@app.get("/ping")
def ping():
    logger.info("[LLM Agent] /ping recibido")
    return {"pong": True}

# —————————————————————————————————————————————————————————————————————————————
# HILO DE REGISTRO A2A
# —————————————————————————————————————————————————————————————————————————————
def register_loop():
    global agent_id
    logger.info("[LLM Agent] register_loop: iniciando…")

    payload = AgentInfo(
        name="llm_agent",
        callback_url=CALLBACK_URL,
        capabilities={"role": "sql_to_text"},
        agent_id=FIXED_AGENT_ID
    ).model_dump(exclude_none=True)
    payload["callback_url"] = str(payload["callback_url"])

    time.sleep(5)
    for i in range(5):
        try:
            resp = requests.post(f"{MCP_URL}/agent/register", json=payload, timeout=3)
            resp.raise_for_status()
            agent_id = resp.json()["agent_id"]
            logger.info(f"[LLM Agent] registrado con id={agent_id}")
            return
        except Exception as e:
            wait = 2 ** i
            logger.warning(f"[LLM Agent] intento {i+1} fallo ({e}), retry en {wait}s")
            time.sleep(wait)
    raise RuntimeError("No pudo registrarse en MCP tras varios intentos")

# —————————————————————————————————————————————————————————————————————————————
# HILO DE HEARTBEAT A2A
# —————————————————————————————————————————————————————————————————————————————
def heartbeat_loop():
    # Envía un Envelope tipo 'heartbeat' cada HEARTBEAT_INTERVAL segundos
    # Espera a que el agente esté registrado
    time.sleep(HEARTBEAT_INTERVAL)
    while True:
        if agent_id:
            env = Envelope(
                version="1.0",
                message_id=str(uuid4().hex),
                timestamp=datetime.now(timezone.utc),
                type="heartbeat",
                sender=agent_id,
                recipient=agent_id,     # el broker ignora recipient==sender
                payload={}
            )
            # serializar timestamp
            j = env.model_dump(mode="json")
            try:
                requests.post(f"{MCP_URL}/agent/heartbeat", json=j, timeout=3).raise_for_status()
            except:
                pass
        time.sleep(HEARTBEAT_INTERVAL)

@app.on_event("startup")
def startup_event():
    threading.Thread(target=register_loop, daemon=True).start()
    threading.Thread(target=heartbeat_loop, daemon=True).start()

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

    logger.info(f"[LLM Agent] /query recibida: {req.pregunta}")
    loop = asyncio.get_running_loop()

    # 2) Generar SQL
    logger.info("[LLM Agent] empezando a generar sql…")
    sql: str = await loop.run_in_executor(None, generar_sql, req.pregunta)
    logger.info(f"[LLM Agent] SQL generado: {sql}")

    # 3) Descubrir dinámicamente destinatario mediante Service Cards
    try:
        resp = requests.get(
            f"{MCP_URL}/agent/services",
            params={"service": "consulta_ventas"},
            timeout=5
        )
        resp.raise_for_status()
        svc_cards = resp.json()  # es un dict: {agent_id: card, ...}
        # filtra entre los agentes online
        candidates = [
            (aid, card)
            for aid, card in svc_cards.items()
            if card.get("online")
        ]
        if not candidates:
            raise HTTPException(502, "No hay agentes de ventas online")
        # elegir el primero
        recipient_id, recipient_card = candidates[0]
    except Exception as e:
        raise HTTPException(502, f"Error resolviendo Service Cards: {e}")
    
    # 4) Construir mensaje A2A
    corr = uuid4().hex
    msg = A2AMessage(
        message_id=corr,
        sender=agent_id,
        recipient=recipient_id,
        timestamp=datetime.now(timezone.utc),
        type="query",
        body={"sql": sql, "correlation_id": corr}
    )

    # 5) Envolver en Envelope y enviar al broker
    env = Envelope(
        version="1.0",
        message_id=msg.message_id,
        timestamp=datetime.now(timezone.utc),
        type=msg.type,
        sender=msg.sender,
        recipient=msg.recipient,
        payload=msg.model_dump()
    )

    # Serializar el Envelope a dict, y asegurarnos de que timestamp sea ISO
    envelope_dict = env.model_dump(mode="json")

    pending[corr] = loop.create_future()
    logger.info(f"[LLM Agent] Enviando envelope A2A a {recipient_id}")

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

    # 6) Generar respuesta
    logger.info("[LLM Agent] empezando generar_respuesta…")
    respuesta: str = await loop.run_in_executor(None, generar_respuesta, req.pregunta, datos)
    logger.info("[LLM Agent] terminado generar_respuesta")

    pending.pop(corr, None)
    logger.info("[LLM Agent] respuesta final lista")
    return {"sql": sql, "respuesta": respuesta}

# —————————————————————————————————————————————————————————————————————————————
@app.post("/inbox")
# Recibe un Envelope A2A. 
async def inbox(env: Envelope):
    # Ignorar los heartbeats
    if env.type == "heartbeat":
        logger.info(f"[Ventas Agent] heartbeat recibido de {env.sender}")
        return {"status": "heartbeat received"}
    if env.type == "ack":
        try:
            ack_msg = A2AMessage.model_validate(env.payload)
            corr = ack_msg.body.get("correlation_id")
            logger.info(f"[LLM Agent] ACK recibido para mensaje {corr}")
        except Exception as e:
            logger.warning(f"[LLM Agent] ACK recibido mal formado: {e}")
        return {"status": "ack recibido"}

    
    # 1) Desempaquetar el Envelope
    msg = A2AMessage.model_validate(env.payload)
    corr = msg.body.get("correlation_id")
    logger.info(f"[LLM Agent] inbox recibido correlation_id={corr} (pending={list(pending.keys())})")
    
    # 2) Envía ACK inmediato al recibir un Envelope
    ack_envelope = Envelope(
        version="1.0",
        message_id=str(uuid4().hex),
        timestamp=datetime.now(timezone.utc),
        type="ack",
        sender=agent_id,
        recipient=env.sender,
        payload={
            "status": "received",
            "correlation_id": env.message_id
        }
    )
    # Enviar ACK al MCP
    requests.post(f"{MCP_URL}/agent/send", json=ack_envelope.model_dump(mode="json"), timeout=5)

    if msg.type == "response" and corr in pending:
        fut = pending[corr]
        if not fut.done():
            fut.set_result(msg.body.get("resultado", []))
            return {"status": "ok"}
        
    return {"status": "ignored"}

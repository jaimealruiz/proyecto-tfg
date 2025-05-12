# agents/ventas_agent/main.py

import threading
import time
import os
import requests
from uuid import uuid4
from datetime import datetime, timezone
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException
from server.a2a_models import A2AMessage, AgentInfo, Envelope

app = FastAPI(title="Ventas Agent (A2A)")

# Configurar logger para que use el mismo handler de Uvicorn
logger = logging.getLogger("uvicorn.error")

# —————————————————————————————————————————————————————————————————————————————
# CONFIGURACIÓN DESDE ENTORNO
# —————————————————————————————————————————————————————————————————————————————
# URL base del MCP (service name en Docker Compose)
MCP_URL = os.getenv("MCP_URL", "http://mcp-server:8000")
# ID fijo para este agente, leído de .env
FIXED_AGENT_ID = os.getenv("VENTAS_AGENT_ID")
# Intervalo de heartbeat en segundos
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "30"))


# Se almacenará aquí el agent_id tras registrarse
agent_id: Optional[str] = None

# —————————————————————————————————————————————————————————————————————————————
# HILO DE REGISTRO A2A
# —————————————————————————————————————————————————————————————————————————————
def register_loop():
    global agent_id

    # 1) Preparamos payload de registro con ID fijo
    reg = AgentInfo(
        name="ventas_agent",
        callback_url=os.getenv("CALLBACK_URL", "http://ventas-agent:8002/inbox"),
        capabilities={"tool": "consulta_ventas"},
        agent_id=FIXED_AGENT_ID
    ).model_dump(exclude_none=True)
    reg["callback_url"] = str(reg["callback_url"])

    # 2) Pequeña espera para que MCP arranque
    time.sleep(5)

    # 3) Intentos exponenciales de registro
    for attempt in range(5):
        try:
            resp = requests.post(f"{MCP_URL}/agent/register", json=reg, timeout=3)
            resp.raise_for_status()
            agent_id = resp.json()["agent_id"]
            logger.info(f"[Ventas Agent] registrado en MCP con id={agent_id}")
            return
        except Exception as e:
            wait = 2 ** attempt
            logger.warning(f"[Ventas Agent] intento {attempt+1} de registro fallido ({e}), retry en {wait}s...")
            time.sleep(wait)

    logger.error("[Ventas Agent] ERROR: no se pudo registrar en MCP tras varios intentos")

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
            j = env.model_dump()
            j["timestamp"] = env.timestamp.isoformat()
            try:
                requests.post(f"{MCP_URL}/agent/heartbeat", json=j, timeout=3).raise_for_status()
            except:
                pass
        time.sleep(30)

@app.on_event("startup")
def startup_event():
    threading.Thread(target=register_loop, daemon=True).start()
    threading.Thread(target=heartbeat_loop, daemon=True).start()

@app.post("/inbox")
# Recibe un Envelope A2A
def inbox(env: Envelope):
    # Ignorar los heartbeats
    if env.type == "heartbeat":
        logger.info(f"[Ventas Agent] heartbeat recibido de {env.sender}")
        return {"status": "heartbeat received"}
    # 1) Desempaquetar el Envelope
    logger.info(f"[Ventas Agent] /inbox envelope tipo={env.type}")
    try:
        msg = A2AMessage.model_validate(env.payload)
    except Exception as e:
        logger.error(f"[Ventas Agent] error validando A2AMessage: {e}")
        raise HTTPException(400, f"Payload inválido: {e}")

    # 2) Validar que es una query
    if msg.type != "query" or "sql" not in msg.body or "correlation_id" not in msg.body:
        raise HTTPException(400, "Mensaje inválido: debe incluir type='query', body.sql y body.correlation_id")

    sql = msg.body["sql"]
    corr = msg.body["correlation_id"]
    logger.info(f"[Ventas Agent] consulta recibida (corr={corr}): {sql}")

    # 3) Ejecutar consulta SQL vía MCP/tool/consulta
    try:
        tool_resp = requests.get(
            f"{MCP_URL}/tool/consulta",
            params={"sql": sql},
            timeout=10
        )
        tool_resp.raise_for_status()
    except Exception as e:
        raise HTTPException(502, f"Error llamando al MCP/tool: {e}")

    resultados = tool_resp.json().get("resultado", [])

    # 4) Construir A2AMessage de respuesta
    reply = A2AMessage(
        message_id=str(uuid4()),
        sender=agent_id,
        recipient=msg.sender,
        timestamp=datetime.now(timezone.utc).isoformat(),
        type="response",
        body={
            "resultado": resultados,
            "correlation_id": corr
        }
    )

    # 5) Envolver en Envelope y reenviar al broker
    env_out = Envelope(
        version="1.0",
        message_id=reply.message_id,
        timestamp=datetime.now(timezone.utc),
        type=reply.type,
        sender=reply.sender,
        recipient=reply.recipient,
        payload=reply.model_dump()
    )
    # Serializar timestamp a ISO
    out_dict = env_out.model_dump()
    out_dict["timestamp"] = env_out.timestamp.isoformat()

    logger.info(f"[Ventas Agent] reenviando respuesta A2A (corr={corr}) a broker")
    try:
        send_resp = requests.post(
            f"{MCP_URL}/agent/send",
            json=out_dict,
            timeout=5
        )
        send_resp.raise_for_status()
    except Exception as e:
        raise HTTPException(502, f"Error reenviando respuesta A2A: {e}")

    return {"status": "ok"}

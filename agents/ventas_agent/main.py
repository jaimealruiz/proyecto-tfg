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
from server.a2a_models import A2AMessage, AgentInfo

app = FastAPI(title="Ventas Agent (A2A)")

# Configurar logger para que use el mismo handler de Uvicorn
logger = logging.getLogger("uvicorn.error")

# URL base del MCP (service name en Docker Compose)
MCP_URL = os.getenv("MCP_URL", "http://mcp-server:8000")
# ID fijo para este agente, leído de .env
FIXED_AGENT_ID = os.getenv("VENTAS_AGENT_ID")
print(f"[Ventas Agent] FIXED_AGENT_ID={FIXED_AGENT_ID!r}", flush=True)

# Se almacenará aquí el agent_id tras registrarse
agent_id: Optional[str] = None

def register_loop():
    global agent_id

    # Preparamos payload de registro con ID fijo
    registration_payload = AgentInfo(
        name="ventas_agent",
        callback_url=os.getenv("CALLBACK_URL", "http://ventas-agent:8002/inbox"),
        capabilities={"tool": "consulta_ventas"},
        agent_id=FIXED_AGENT_ID
    ).model_dump(exclude_none=True)
    registration_payload["callback_url"] = str(registration_payload["callback_url"])

    # Espera inicial para que MCP tenga tiempo de arrancar y resolverse el DNS
    time.sleep(5)

    # Intentos exponenciales de registro
    for attempt in range(5):
        try:
            resp = requests.post(
                f"{MCP_URL}/agent/register",
                json=registration_payload,
                timeout=3
            )
            resp.raise_for_status()
            agent_id = resp.json()["agent_id"]
            logger.info(f"[Ventas Agent] registrado en MCP con id={agent_id}")
            return
        except requests.RequestException as e:
            wait = 2 ** attempt
            logger.warning(
                f"[Ventas Agent] intento {attempt+1} de registro fallido ({e}), reintentando en {wait}s..."
            )
            time.sleep(wait)

    logger.error("[Ventas Agent] ERROR: no se pudo registrar en MCP tras varios intentos")

@app.on_event("startup")
def startup_event():
    # Arrancamos el registro en un hilo daemon para no bloquear el startup
    threading.Thread(target=register_loop, daemon=True).start()

@app.post("/inbox")
def inbox(msg: A2AMessage):
    """
    Endpoint donde el MCP reenviará los mensajes A2A para este agente.
    Procesamos únicamente type="query" con body.sql y body.correlation_id.
    """
    if msg.type != "query" or "sql" not in msg.body or "correlation_id" not in msg.body:
        raise HTTPException(
            400,
            "Mensaje inválido: debe incluir type='query', body.sql y body.correlation_id"
        )

    sql = msg.body["sql"]
    correlation_id = msg.body["correlation_id"]

    # Ejecutar consulta SQL vía MCP/tool/consulta
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

    # Construir mensaje de respuesta, preservando correlation_id
    reply = A2AMessage(
        message_id=str(uuid4()),
        sender=agent_id,
        recipient=msg.sender,
        timestamp=datetime.now(timezone.utc).isoformat(),
        type="response",
        body={
            "resultado": resultados,
            "correlation_id": correlation_id
        }
    )

    # Enviar respuesta A2A de vuelta al MCP
    try:
        send_resp = requests.post(
            f"{MCP_URL}/agent/send",
            json=reply.model_dump(),
            timeout=5
        )
        send_resp.raise_for_status()
    except Exception as e:
        raise HTTPException(502, f"Error reenviando respuesta A2A: {e}")

    return {"status": "ok"}

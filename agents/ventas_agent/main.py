# agents/ventas_agent/main.py

import threading
import time
import os
import requests
from uuid import uuid4
from datetime import datetime, timezone
import logging
from typing import Optional, Dict, Tuple, Any
from fastapi import FastAPI, HTTPException
from server.a2a_models import A2AMessage, AgentInfo, Envelope
from requests.exceptions import ReadTimeout

import asyncio

# —————————————————————————————————————————————————————————————————————————————
app = FastAPI(title="Ventas Agent (A2A)")
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

# Estado de retransmisiones: message_id → (Envelope, attempts, next_timeout)
pending_acks: Dict[str, Tuple[Envelope, int, float]] = {}
BASE_ACK_TIMEOUT = 5.0    # segundos antes del primer reintento
MAX_ACK_ATTEMPTS = 3      # máximo de envíos por mensaje

# Se almacenará aquí el agent_id tras registrarse
agent_id: Optional[str] = None

# —————————————————————————————————————————————————————————————————————————————
# Helper para enviar ACKs
# —————————————————————————————————————————————————————————————————————————————
def _send_ack(env_dict: Dict[str, Any]):
    """
    Envía un ACK al broker sin bloquear el handler.
    """
    try:
        logger.info(f"[LLM Agent] Lanzando hilo de envío ACK {env_dict['message_id']}")
        requests.post(f"{MCP_URL}/agent/send", json=env_dict, timeout=15).raise_for_status()
        logger.info("[Ventas Agent] ACK enviado correctamente")
    except Exception as e:
        logger.error(f"[Ventas Agent] Error enviando ACK: {e}")
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
            j = env.model_dump(mode="json")
            try:
                requests.post(f"{MCP_URL}/agent/heartbeat", json=j, timeout=3).raise_for_status()
            except:
                pass
        time.sleep(30)

@app.on_event("startup")
def startup_event():
    threading.Thread(target=register_loop, daemon=True).start()
    threading.Thread(target=heartbeat_loop, daemon=True).start()

# —————————————————————————————————————————————————————————————————————————————
# RETRANSMISIÓN DE MENSAJES A2A SI NO LLEGA ACK
# —————————————————————————————————————————————————————————————————————————————
async def send_with_retries(env: Envelope):
    
    # Envía un Envelope y, si no llega ACK, lo reintenta con backoff exponencial.
    envelope_dict = env.model_dump(mode="json")
    msg_id = env.message_id
    attempts = 0
    timeout = BASE_ACK_TIMEOUT

    # Registrar el primer estado
    pending_acks[msg_id] = (env, attempts, timeout)

    while attempts < MAX_ACK_ATTEMPTS:
        attempts += 1
        try:
            # Envío real
            requests.post(f"{MCP_URL}/agent/send", json=envelope_dict, timeout=20).raise_for_status()
            logger.info(f"[LLM Agent] Envío {msg_id}, intento {attempts}")
        except ReadTimeout:
            logger.warning(f"[LLM Agent] Primer intento de envío {msg_id} superó timeout... reintentando")
        except Exception as e:
            logger.error(f"[LLM Agent] Error enviando {msg_id} (intento {attempts}): {e}")

        # Esperar el timeout antes de posible reintento
        await asyncio.sleep(timeout)

        # Si ya recibimos ACK, salimos
        if msg_id not in pending_acks:
            return

        # Ajustar backoff
        timeout *= 2
        pending_acks[msg_id] = (env, attempts, timeout)

    # Si expiraron los intentos
    logger.error(f"[LLM Agent] No se recibió ACK para {msg_id} tras {MAX_ACK_ATTEMPTS} intentos")
    pending_acks.pop(msg_id, None)

# —————————————————————————————————————————————————————————————————————————————
# RECEPCIÓN DE MENSAJES A2A
# —————————————————————————————————————————————————————————————————————————————
@app.post("/inbox")
# Recibe un Envelope A2A
async def inbox(env: Envelope):
    # Ignorar los heartbeats
    if env.type == "heartbeat":
        logger.info(f"[Ventas Agent] heartbeat recibido de {env.sender}")
        return {"status": "heartbeat received"}
    
    # Manejar ACKs entrantes
    if env.type == "ack":
        try:
            ack_msg = A2AMessage.model_validate(env.payload)
            corr = ack_msg.body.get("correlation_id")
            if corr in pending_acks:
                pending_acks.pop(corr)
                logger.info(f"[Ventas Agent] ACK recibido para mensaje {corr}, cancelando retransmisiones.")
        except Exception as e:
            logger.warning(f"[Ventas Agent] ACK mal formado: {e}")
        return {"status": "ack recibido"}
    
    # 1) Desempaquetar el Envelope
    logger.info(f"[Ventas Agent] /inbox envelope tipo={env.type}")
    try:
        msg = A2AMessage.model_validate(env.payload)
    except Exception as e:
        logger.error(f"[Ventas Agent] error validando A2AMessage: {e}")
        raise HTTPException(400, f"Payload inválido: {e}")
    
    # 2) Envía ACK inmediato al recibir un Envelope
    ack_msg = A2AMessage(
        message_id=str(uuid4()),
        sender=agent_id,
        recipient=env.sender,
        timestamp=datetime.now(timezone.utc),
        type="ack",
        body={
            "status": "received",
            "correlation_id": env.message_id
        }
    )
    ack_env = Envelope(
        version="1.0",
        message_id=ack_msg.message_id,
        timestamp=datetime.now(timezone.utc),
        type="ack",
        sender=ack_msg.sender,
        recipient=ack_msg.recipient,
        payload=ack_msg.model_dump(mode="json")
    )
    env_dict = ack_env.model_dump(mode="json")
    threading.Thread(target=_send_ack, args=(env_dict,), daemon=True).start()

    # 3) Validar que es una query
    if msg.type != "query" or "sql" not in msg.body or "correlation_id" not in msg.body:
        raise HTTPException(400, "Mensaje inválido: debe incluir type='query', body.sql y body.correlation_id")

    # 4) Ejecutar consulta SQL vía MCP/tool/consulta
    sql = msg.body["sql"]
    corr = msg.body["correlation_id"]
    logger.info(f"[Ventas Agent] consulta recibida (corr={corr}): {sql}")
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

    # 5) Construir A2AMessage de respuesta
    reply = A2AMessage(
        message_id=str(uuid4()),
        sender=agent_id,
        recipient=msg.sender,
        timestamp=datetime.now(timezone.utc),
        type="response",
        body={
            "resultado": resultados,
            "correlation_id": corr
        }
    )

    # 6) Envolver en Envelope y reenviar al broker
    env_out = Envelope(
        version="1.0",
        message_id=reply.message_id,
        timestamp=datetime.now(timezone.utc),
        type=reply.type,
        sender=reply.sender,
        recipient=reply.recipient,
        payload=reply.model_dump(mode="json")
    )
    logger.info(f"[Ventas Agent] reenviando respuesta A2A (corr={corr}) a broker")
    
    # 7) Envío con retransmisiones y ACKs
    await send_with_retries(env_out)

    return {"status": "ok"}

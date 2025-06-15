import threading
import time
import os
import requests
import httpx
from uuid import uuid4
from datetime import datetime, timezone
import logging
from typing import Optional, Dict, Tuple, Any
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from server.a2a_models import A2AMessage, AgentInfo, Envelope
from requests.exceptions import ReadTimeout

import asyncio
from security.security import sign_envelope, verify_jwt_token
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
AGENT_NAME_MAP: Dict[str,str] = {}
LOGICAL_NAME = "ventas_agent" 
# —————————————————————————————————————————————————————————————————————————————
# Helper para enviar ACKs
# —————————————————————————————————————————————————————————————————————————————
def _send_ack(env_dict: Dict[str, Any]):
    """
    Envía un Envelope firmado al broker en un hilo separado sin bloquear el handler.
    """
    try:
        logical_iss = AGENT_NAME_MAP.get(agent_id, agent_id)
        token = sign_envelope(
            env_dict,
            issuer=logical_iss,
            audience=os.getenv("BROKER_ID", "mcp-server")
        )
        logger.info(f"[{LOGICAL_NAME}] Lanzando hilo de envío ACK {env_dict['message_id']}")
        requests.post(
            f"{MCP_URL}/agent/send",
            json={"jwt": token},
            timeout=15
        ).raise_for_status()
        logger.info("[{LOGICAL_NAME}] ACK enviado correctamente")
    except Exception as e:
        logger.error(f"[{LOGICAL_NAME}] Error enviando ACK: {e}")
# —————————————————————————————————————————————————————————————————————————————
# HILO DE REGISTRO A2A
# —————————————————————————————————————————————————————————————————————————————
def register_loop():
    global agent_id

    # 1) Preparamos payload de registro con ID fijo
    reg = AgentInfo(
        name=LOGICAL_NAME,
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
            # Guardamos el mapeo dinámico → nombre lógico
            AGENT_NAME_MAP[agent_id] = LOGICAL_NAME
            logger.info(f"[{LOGICAL_NAME}] registrado con id dinámico={agent_id} (logical={LOGICAL_NAME})")
            return
        except Exception as e:
            wait = 2 ** attempt
            logger.warning(f"[{LOGICAL_NAME}] intento {attempt+1} de registro fallido ({e}), retry en {wait}s...")
            time.sleep(wait)

    logger.error("[{LOGICAL_NAME}] ERROR: no se pudo registrar en MCP tras varios intentos")

# —————————————————————————————————————————————————————————————————————————————
# HILO DE HEARTBEAT A2A
# —————————————————————————————————————————————————————————————————————————————
def heartbeat_loop():
    # Envía un Envelope tipo 'heartbeat' cada HEARTBEAT_INTERVAL segundos
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
            # serializar y firmar
            env_dict = env.model_dump(mode="json")
            logical_iss = AGENT_NAME_MAP.get(agent_id, agent_id)
            token = sign_envelope(env_dict, issuer=logical_iss, audience=os.getenv("BROKER_ID", "mcp-server"))
            try:
                requests.post(f"{MCP_URL}/agent/heartbeat", json={"jwt": token}, timeout=3).raise_for_status()
            except:
                pass
        time.sleep(HEARTBEAT_INTERVAL)

@app.on_event("startup")
def startup_event():
    threading.Thread(target=register_loop, daemon=True).start()
    threading.Thread(target=heartbeat_loop, daemon=True).start()

# —————————————————————————————————————————————————————————————————————————————
# ENVÍO DE MENSAJES A2A CON RETRIES ASÍNCRONO PURO
# —————————————————————————————————————————————————————————————————————————————
async def send_with_retries(env: Envelope):
    """
    Envía un Envelope al broker y, si no llega ACK, reintenta
    con backoff exponencial de manera asíncrona.
    """
    env_dict = env.model_dump(mode="json")
    msg_id = env.message_id
    attempts = 0
    timeout = BASE_ACK_TIMEOUT
    pending_acks[msg_id] = (env, attempts, timeout)

    logical_iss = AGENT_NAME_MAP.get(agent_id, agent_id)
    async with httpx.AsyncClient(timeout=None) as client:
        while attempts < MAX_ACK_ATTEMPTS:
            attempts += 1
            try:
                token = sign_envelope(
                    env_dict,
                    issuer=logical_iss,
                    audience=os.getenv("BROKER_ID", "mcp-server")
                )
                resp = await client.post(
                    f"{MCP_URL}/agent/send",
                    json={"jwt": token},
                    timeout=20.0
                )
                resp.raise_for_status()
                logger.info(f"[{LOGICAL_NAME}] Envío {msg_id} OK en intento {attempts}")
                return
            except httpx.ReadTimeout:
                logger.warning(f"[{LOGICAL_NAME}] Timeout en intento {attempts} de {msg_id}, reintentando")
            except Exception as e:
                logger.error(f"[{LOGICAL_NAME}] Error en intento {attempts} de {msg_id}: {e}")

            # esperar antes de reintentar
            await asyncio.sleep(timeout)

            # si ya llegó ACK, salir
            if msg_id not in pending_acks:
                return

            # incrementar backoff
            timeout *= 2
            pending_acks[msg_id] = (env, attempts, timeout)

    logger.error(f"[{LOGICAL_NAME}] No se recibió ACK para {msg_id} tras {MAX_ACK_ATTEMPTS} intentos")
    pending_acks.pop(msg_id, None)

# —————————————————————————————————————————————————————————————————————————————
# RECEPCIÓN DE MENSAJES A2A
# —————————————————————————————————————————————————————————————————————————————
@app.post("/inbox")
async def inbox(request: Request, background_tasks: BackgroundTasks):
    """
    Handler de A2A inbound:
    1) Verifica JWT y desempaqueta Envelope
    2) Ignora heartbeats y procesa ACKs
    3) Envía ACK inmediato
    4) Ejecuta la query y prepara respuesta
    5) Programa reenvío de la respuesta al broker en background
    """
    # 1) Parsear y verificar JWT
    try:
        body = await request.json()
        token = body.get("jwt")
        env_dict = verify_jwt_token(token)
        env = Envelope.model_validate(env_dict)
    except Exception as e:
        raise HTTPException(400, f"JWT inválido o verificación fallida: {e}")

    # 2) Filtrar heartbeats
    if env.type == "heartbeat":
        logger.info(f"[{LOGICAL_NAME}] heartbeat recibido de {env.sender}")
        return {"status": "heartbeat received"}

    # 3) Procesar ACK entrante
    if env.type == "ack":
        try:
            ack_msg = A2AMessage.model_validate(env.payload)
            corr = ack_msg.body.get("correlation_id")
            if corr in pending_acks:
                pending_acks.pop(corr)
                logger.info(f"[{LOGICAL_NAME}] ACK recibido para mensaje {corr}, cancelando retransmisiones.")
        except Exception as e:
            logger.warning(f"[{LOGICAL_NAME}] ACK mal formado: {e}")
        return {"status": "ack recibido"}

    # 4) Desempaquetar query
    logger.info(f"[{LOGICAL_NAME}] /inbox envelope tipo={env.type}")
    try:
        msg = A2AMessage.model_validate(env.payload)
    except Exception as e:
        logger.error(f"[{LOGICAL_NAME}] error validando A2AMessage: {e}")
        raise HTTPException(400, f"Payload inválido: {e}")

    # 5) Enviar ACK inmediato
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
    threading.Thread(target=_send_ack, args=(ack_env.model_dump(mode="json"),), daemon=True).start()

    # 6) Validar que sea tipo query
    if msg.type != "query" or "sql" not in msg.body or "correlation_id" not in msg.body:
        raise HTTPException(400, "Mensaje inválido: debe incluir type='query', body.sql y body.correlation_id")

    # 7) Ejecutar la consulta contra MCP/tool/consulta
    sql = msg.body["sql"]
    corr = msg.body["correlation_id"]
    logger.info(f"[{LOGICAL_NAME}] consulta recibida (corr={corr}): {sql}")
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

    # 8) Construir mensaje de respuesta A2A
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
    env_out = Envelope(
        version="1.0",
        message_id=reply.message_id,
        timestamp=datetime.now(timezone.utc),
        type=reply.type,
        sender=reply.sender,
        recipient=reply.recipient,
        payload=reply.model_dump(mode="json")
    )
    logger.info(f"[{LOGICAL_NAME}] reenviando respuesta A2A (corr={corr}) a broker")

    # 9) Programar reintentos de envío en background
    background_tasks.add_task(send_with_retries, env_out)

    return {"status": "accepted"}
import os
import time
import threading
import asyncio
from uuid import uuid4
from datetime import datetime, timezone
from typing import Optional, Any, Dict, Tuple
import logging
import httpx
import requests
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from server.a2a_models import A2AMessage, AgentInfo, Envelope
from utils.model_utils import generar_sql, generar_respuesta
from requests.exceptions import ReadTimeout as RequestsReadTimeout
from security.security import sign_envelope, verify_jwt_token

# —————————————————————————————————————————————————————————————————————————————
app = FastAPI(title="LLM Agent (A2A)")
logger = logging.getLogger("uvicorn.error")

# —————————————————————————————————————————————————————————————————————————————
# CONFIGURACIÓN DESDE ENTORNO
# —————————————————————————————————————————————————————————————————————————————
MCP_URL        = os.getenv("MCP_URL",      "http://mcp-server:8000")
CALLBACK_URL   = os.getenv("CALLBACK_URL", "http://llm-agent:8003/inbox")
FIXED_AGENT_ID = os.getenv("LLM_AGENT_ID")
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "30"))

# Estado de retransmisiones y promesas de respuesta
pending_acks: Dict[str, Tuple[Envelope, int, float]] = {}
pending: Dict[str, asyncio.Future] = {}
BASE_ACK_TIMEOUT = 5.0  # segundos antes del primer reintento
MAX_ACK_ATTEMPTS = 3

agent_id: Optional[str] = None
AGENT_NAME_MAP: Dict[str,str] = {}
LOGICAL_NAME = "llm_agent"

# —————————————————————————————————————————————————————————————————————————————
# ENDPOINT DE DIAGNÓSTICO
# —————————————————————————————————————————————————————————————————————————————
@app.get("/ping")
def ping():
    logger.info(f"[{LOGICAL_NAME}] /ping recibido")
    return {"pong": True}

# —————————————————————————————————————————————————————————————————————————————
# Helper para enviar ACKs en hilo
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
        logger.info(f"[{LOGICAL_NAME}] ACK enviado correctamente")
    except Exception as e:
        logger.error(f"[{LOGICAL_NAME}] Error enviando ACK: {e}")

# —————————————————————————————————————————————————————————————————————————————
# HILO DE REGISTRO A2A
# —————————————————————————————————————————————————————————————————————————————
def register_loop():
    global agent_id
    logger.info(f"[{LOGICAL_NAME}] register_loop: iniciando…")

    payload = AgentInfo(
        name=LOGICAL_NAME,
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
            AGENT_NAME_MAP[agent_id] = LOGICAL_NAME
            logger.info(f"[{LOGICAL_NAME}] registrado con id dinámico={agent_id}")
            return
        except Exception as e:
            wait = 2 ** i
            logger.warning(f"[{LOGICAL_NAME}] intento {i+1} fallo ({e}), retry en {wait}s")
            time.sleep(wait)
    raise RuntimeError("No pudo registrarse en MCP tras varios intentos")

# —————————————————————————————————————————————————————————————————————————————
# HILO DE HEARTBEAT A2A
# —————————————————————————————————————————————————————————————————————————————
def heartbeat_loop():
    time.sleep(HEARTBEAT_INTERVAL)
    while True:
        if agent_id:
            env = Envelope(
                version="1.0",
                message_id=str(uuid4().hex),
                timestamp=datetime.now(timezone.utc),
                type="heartbeat",
                sender=agent_id,
                recipient=agent_id,
                payload={}
            )
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
                token = sign_envelope(env_dict, issuer=logical_iss, audience=os.getenv("BROKER_ID", "mcp-server"))
                resp = await client.post(
                    f"{MCP_URL}/agent/send", json={"jwt": token}, timeout=20.0
                )
                resp.raise_for_status()
                logger.info(f"[{LOGICAL_NAME}] Envío {msg_id} OK en intento {attempts}")
                return
            except httpx.ReadTimeout:
                logger.warning(f"[{LOGICAL_NAME}] Timeout intento {attempts}, reintentando")
            except Exception as e:
                logger.error(f"[{LOGICAL_NAME}] Error intento {attempts}: {e}")

            await asyncio.sleep(timeout)
            if msg_id not in pending_acks:
                return
            timeout *= 2
            pending_acks[msg_id] = (env, attempts, timeout)

    logger.error(f"[{LOGICAL_NAME}] No se recibió ACK para {msg_id} tras {MAX_ACK_ATTEMPTS} intentos")
    pending_acks.pop(msg_id, None)

# —————————————————————————————————————————————————————————————————————————————
# ESQUEMA DE ENVÍO A2A (/query)
# —————————————————————————————————————————————————————————————————————————————
class ConsultaRequest(BaseModel):
    pregunta: str

@app.post("/query")
async def hacer_consulta(request: Request):
    # 1) validar JSON entrante
    try:
        body = await request.json()
        req = ConsultaRequest(**body)
    except Exception:
        return JSONResponse(status_code=400, content={"error": "JSON inválido. Debe ser {'pregunta':'...'}."})

    if agent_id is None:
        raise HTTPException(503, "Aún no registrado en MCP; inténtalo más tarde.")

    logger.info(f"[{LOGICAL_NAME}] /query recibida: {req.pregunta}")
    loop = asyncio.get_running_loop()

    # 2) Generar SQL en pool de threads
    logger.info(f"[{LOGICAL_NAME}] empezando a generar consulta…")
    sql: str = await loop.run_in_executor(None, generar_sql, req.pregunta)
    logger.info(f"[{LOGICAL_NAME}] SQL generado: {sql}")

    # 3) Descubrir agente de ventas
    try:
        svc = await loop.run_in_executor(None, lambda: requests.get(
            f"{MCP_URL}/agent/services",
            params={"service": "consulta_ventas"},
            timeout=5
        ).json())
        candidates = [(aid, card) for aid, card in svc.items() if card.get("online")]
        if not candidates:
            raise RuntimeError("No hay agentes de ventas online")
        recipient_id, _ = candidates[0]
    except Exception as e:
        raise HTTPException(502, f"Error resolviendo Service Cards: {e}")

    # 4) Construir A2AMessage y Envelope
    corr = uuid4().hex
    msg = A2AMessage(
        message_id=corr,
        sender=agent_id,
        recipient=recipient_id,
        timestamp=datetime.now(timezone.utc),
        type="query",
        body={"sql": sql, "correlation_id": corr}
    )
    env = Envelope(
        version="1.0",
        message_id=msg.message_id,
        timestamp=datetime.now(timezone.utc),
        type=msg.type,
        sender=msg.sender,
        recipient=msg.recipient,
        payload=msg.model_dump(mode="json")
    )

    # 5) Registrar futura respuesta y enviar
    pending[corr] = loop.create_future()
    logger.info(f"[{LOGICAL_NAME}] Enviando envelope A2A a {recipient_id}")
    await send_with_retries(env)

    # 6) Esperar respuesta o timeout
    try:
        datos = await asyncio.wait_for(pending[corr], timeout=30)
    except asyncio.TimeoutError:
        pending.pop(corr, None)
        raise HTTPException(504, "Timeout esperando respuesta de ventas-agent")

    # 7) Generar texto de vuelta
    logger.info(f"[{LOGICAL_NAME}] empezando a generar respuesta…")
    respuesta: str = await loop.run_in_executor(None, generar_respuesta, req.pregunta, datos)
    logger.info(f"[{LOGICAL_NAME}] respuesta final lista")

    pending.pop(corr, None)
    return {"sql": sql, "respuesta": respuesta}

# —————————————————————————————————————————————————————————————————————————————
# RECEPCIÓN DE MENSAJES A2A
# —————————————————————————————————————————————————————————————————————————————
@app.post("/inbox")
async def inbox(request: Request, background_tasks: BackgroundTasks):
    """
    Handler de A2A inbound:
    1) Verifica JWT y desempaqueta Envelope
    2) Filtra heartbeats y ACKs
    3) Envía ACK inmediato
    4) Ejecuta tool/consulta y prepara respuesta
    5) Programa reenvío de la respuesta al broker en background
    """
    # 1) Verificar JWT
    try:
        body = await request.json()
        token = body.get("jwt")
        env_dict = verify_jwt_token(token)
        env = Envelope.model_validate(env_dict)
    except Exception as e:
        raise HTTPException(400, f"JWT inválido o verificación fallida: {e}")

    # 2) Heartbeats
    if env.type == "heartbeat":
        logger.info(f"[{LOGICAL_NAME}] heartbeat recibido de {env.sender}")
        return {"status": "heartbeat received"}

    # 3) ACKs entrantes
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

    # 5) ACK inmediato
    ack_msg = A2AMessage(
        message_id=str(uuid4()),
        sender=agent_id,
        recipient=env.sender,
        timestamp=datetime.now(timezone.utc),
        type="ack",
        body={"status": "received", "correlation_id": env.message_id}
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

    # 6) Validar tipo query
    if msg.type != "query" or "sql" not in msg.body or "correlation_id" not in msg.body:
        raise HTTPException(400, "Mensaje inválido: debe incluir type='query', body.sql y body.correlation_id")

    # 7) Ejecutar consulta local via MCP/tool/consulta
    sql = msg.body["sql"]
    corr = msg.body["correlation_id"]
    logger.info(f"[{LOGICAL_NAME}] consulta recibida (corr={corr}): {sql}")
    try:
        tool_resp = requests.get(
            f"{MCP_URL}/tool/consulta",
            params={"sql": sql}, timeout=10
        )
        tool_resp.raise_for_status()
    except Exception as e:
        raise HTTPException(502, f"Error llamando al MCP/tool: {e}")
    resultados = tool_resp.json().get("resultado", [])

    # 8) Construir respuesta A2A y programar envío
    reply = A2AMessage(
        message_id=str(uuid4()),
        sender=agent_id,
        recipient=msg.sender,
        timestamp=datetime.now(timezone.utc),
        type="response",
        body={"resultado": resultados, "correlation_id": corr}
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

    background_tasks.add_task(send_with_retries, env_out)

    return {"status": "accepted"}

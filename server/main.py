from fastapi import FastAPI, HTTPException, Query
from a2a_models import AgentInfo, Envelope, ServiceCard
from datetime import datetime, timedelta, timezone
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from typing import Dict, Any, List, Optional
from uuid import uuid4
import requests
import duckdb
import os

# —————————————————————————————————————————————————————————————————————————————
# APP & STORAGE
# —————————————————————————————————————————————————————————————————————————————
app = FastAPI(title="Servidor MCP para Apache Iceberg y A2A Broker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Almacenamiento en memoria de agentes registrados, por cada agent_id:
#   { name, callback_url, capabilities, last_heartbeat (datetime|None) }
AGENTS: Dict[str, dict] = {}

# Almacenamiento adicional de último heartbeat
LAST_HEARTBEAT: Dict[str, datetime] = {}
HEARTBEAT_TIMEOUT = timedelta(seconds=60)
HEARTBEAT_INTERVAL = int(os.getenv("HEARTBEAT_INTERVAL", "30"))

# —————————————————————————————————————————————————————————————————————————————
# DESCUBRIMIENTO DE AGENTES POR CAPACIDAD
# —————————————————————————————————————————————————————————————————————————————
@app.get("/agent/discover", response_model=Dict[str, Any])
def discover_agents(
    role: Optional[str] = Query(None, description="Filtrar por capabilities['role']"),
    tool: Optional[str] = Query(None, description="Filtrar por capabilities['tool']")
):
    """
    Devuelve los agent_id de agentes que cumplan las capacidades solicitadas.
    Si no se pasa ningún filtro, devuelve todos.
    """
    now = datetime.now(timezone.utc)
    found: Dict[str, Any] = {}
    for aid, info in AGENTS.items():
        caps = info.get("capabilities", {})
        if role and caps.get("role") != role:
            continue
        if tool and caps.get("tool") != tool:
            continue
        last = info.get("last_heartbeat")
        found[aid] = {
            "name": info["name"],
            "capabilities": caps,
            "callback_url": info["callback_url"],
            "online": bool(last and (now - last).total_seconds() < 2 * HEARTBEAT_INTERVAL)
        }
    return found

# —————————————————————————————————————————————————————————————————————————————
# REGISTRO DE AGENTES
# —————————————————————————————————————————————————————————————————————————————
@app.post("/agent/register")
def register_agent(info: AgentInfo):
    # Construir dict inicial y manejar agent_id manualmente
    payload = info.model_dump(exclude_none=True)
    # Asignar un agent_id si no viene en payload
    agent_id = payload.get("agent_id") or uuid4().hex
    payload["agent_id"] = agent_id
    # Asegurar que callback_url es str
    payload["callback_url"] = str(payload.get("callback_url"))
    # Guardar en memoria
    AGENTS[agent_id] = payload
    return {"agent_id": agent_id}

# —————————————————————————————————————————————————————————————————————————————
# AGENT CARD: DINAMIC AGENT DISCOVERY
# —————————————————————————————————————————————————————————————————————————————
@app.get("/agent/cards")
# Devuelve el Agent Card de todos los agentes registrados: name, callback_url,
# capabilities, last_heartbeat (ISO) y online (bool)
def agent_cards():
    now = datetime.now(timezone.utc)
    cards: Dict[str, Any] = {}
    for aid, info in AGENTS.items():
        last = info.get("last_heartbeat")
        online = bool(last and (now - last).total_seconds() < (2 * HEARTBEAT_INTERVAL))
        cards[aid] = {
            "agent_id": aid,
            "name": info["name"],
            "callback_url": info["callback_url"],
            "capabilities": info["capabilities"],
            "last_heartbeat": last if last else None,
            "online": online,
        }
    return cards

@app.get("/agent/card/{agent_id}")
# Devuelve el Agent Card del agente con ID dado
def get_agent_card(agent_id: str):
    card = AGENTS.get(agent_id)
    if not card:
        raise HTTPException(404, f"Agent '{agent_id}' no registrado")
    return card

# —————————————————————————————————————————————————————————————————————————————
# SERVICE CARDS: DINAMIC SERVICE DISCOVERY
# —————————————————————————————————————————————————————————————————————————————
@app.get("/agent/services", response_model=Dict[str, Any])
def service_cards(service: str):
    now = datetime.now(timezone.utc)
    results = {}
    for aid, info in AGENTS.items():
        caps = info.get("capabilities", {})
        if caps.get("tool") != service and caps.get("role") != service:
            continue
        last = info.get("last_heartbeat")
        online = bool(last and (now - last).total_seconds() < 2 * HEARTBEAT_INTERVAL)
        results[aid] = {
            "agent_id":      aid,
            "name":          info["name"],
            "callback_url":  info["callback_url"],
            "capabilities":  caps,
            "last_heartbeat": last if last else None,
            "online":        online,
        }
    return results

# —————————————————————————————————————————————————————————————————————————————
# ENVÍO DE MENSAJES JAR-A2A (query/response)
# —————————————————————————————————————————————————————————————————————————————
@app.post("/agent/send")
def send_message(env: Envelope):
    """
    Recibe un Envelope A2A, verifica recipient y reenvía
    únicamente payload al callback_url del destinatario.
    """
    # 1) Asegurarnos de que el destinatario existe
    if env.recipient not in AGENTS:
        raise HTTPException(404, f"Recipient '{env.recipient}' no registrado")

    callback_url = AGENTS[env.recipient]["callback_url"]

    # 2) reenvío HTTP POST -> /inbox del agente
    try:
        # convertir el Envelope a un JSON serializable
        payload = jsonable_encoder(env)
        # convertir datetimes a ISO strings
        resp = requests.post(callback_url, json=payload, timeout=5)
        resp.raise_for_status()
    except Exception as e:
        raise HTTPException(502, f"Error reenviando mensaje A2A: {e}")

    return {"status": "sent"}

# —————————————————————————————————————————————————————————————————————————————
# RECEPCIÓN DE HEARTBEAT A2A
# —————————————————————————————————————————————————————————————————————————————
@app.post("/agent/heartbeat")
def agent_heartbeat(env: Envelope):
    if env.type != "heartbeat":
        raise HTTPException(400, "Tipo de envelope inválido para heartbeat")
    sender = env.sender
    if sender not in AGENTS:
        raise HTTPException(404, f"Agent '{sender}' no registrado")
    # Actualizamos el timestamp
    AGENTS[sender]["last_heartbeat"] = env.timestamp.astimezone(timezone.utc)
    return {"status": "ok"}

# —————————————————————————————————————————————————————————————————————————————
# ESTADO DE AGENTES REGISTRADOS
# —————————————————————————————————————————————————————————————————————————————
@app.get("/agent/status")
def agent_status():
    now = datetime.now(timezone.utc)
    status: Dict[str, Any] = {}
    for aid, info in AGENTS.items():
        last = info.get("last_heartbeat")
        status[aid] = {
            "name": info["name"],
            "last_heartbeat": last if last else None,
            # marcamos online si hemos recibido un latido en los últimos 2 * HEARTBEAT_INTERVAL
            "online": bool(last and (now - last).total_seconds() < (2*HEARTBEAT_INTERVAL))
        }
    return status

# —————————————————————————————————————————————————————————————————————————————
# ENDPOINTS DE CONSULTA MCP
# —————————————————————————————————————————————————————————————————————————————
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'lake.duckdb'))
con = duckdb.connect(DB_PATH)
con.execute("LOAD iceberg;")

@app.get("/tool/consulta")
# Ejecutar consulta MCP
def ejecutar_consulta(sql: str):
    try:
        resultado = con.execute(sql).fetchall()
        columnas = [desc[0] for desc in con.description]
        datos = [dict(zip(columnas, fila)) for fila in resultado]
        return {"resultado": datos}
    except Exception as e:
        return {"error": str(e)}

@app.get("/tool/info/productos")
# Contexto MCP
def obtener_productos():
    try:
        resultado = con.execute("SELECT DISTINCT producto FROM iceberg_space.ventas").fetchall()
        productos = [fila[0] for fila in resultado]
        return {"productos": productos}
    except Exception as e:
        return {"error": str(e)}

@app.get("/tool/info/fechas")
# Contexto MCP
def obtener_rango_fechas():
    try:
        resultado = con.execute("SELECT MIN(fecha), MAX(fecha) FROM iceberg_space.ventas").fetchone()
        return {"min_fecha": str(resultado[0]), "max_fecha": str(resultado[1])}
    except Exception as e:
        return {"error": str(e)}


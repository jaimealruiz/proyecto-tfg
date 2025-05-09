from fastapi import FastAPI, HTTPException
from a2a_models import AgentInfo, Envelope
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from typing import Dict
from uuid import uuid4
import requests
import os

app = FastAPI(title="Servidor MCP para Apache Iceberg y A2A Broker")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Almacenamiento en memoria de agentes registrados
AGENTS: Dict[str, dict] = {}

# --- Endpoints A2A ---

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


# --- Endpoints MCP/tool ---

import duckdb
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'lake.duckdb'))
con = duckdb.connect(DB_PATH)
con.execute("LOAD iceberg;")

@app.get("/tool/consulta")
def ejecutar_consulta(sql: str):
    try:
        resultado = con.execute(sql).fetchall()
        columnas = [desc[0] for desc in con.description]
        datos = [dict(zip(columnas, fila)) for fila in resultado]
        return {"resultado": datos}
    except Exception as e:
        return {"error": str(e)}

@app.get("/tool/info/productos")
def obtener_productos():
    try:
        resultado = con.execute("SELECT DISTINCT producto FROM iceberg_space.ventas").fetchall()
        productos = [fila[0] for fila in resultado]
        return {"productos": productos}
    except Exception as e:
        return {"error": str(e)}

@app.get("/tool/info/fechas")
def obtener_rango_fechas():
    try:
        resultado = con.execute("SELECT MIN(fecha), MAX(fecha) FROM iceberg_space.ventas").fetchone()
        return {"min_fecha": str(resultado[0]), "max_fecha": str(resultado[1])}
    except Exception as e:
        return {"error": str(e)}

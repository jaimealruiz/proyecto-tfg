from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any
import duckdb
import os
import requests

# === CONFIGURACIÓN ===
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'lake.duckdb'))
DUCKDB_CATALOG = "iceberg_space.ventas"

AGENT_ENDPOINTS = {
    "llm_sql_agent": "http://llm-sql-agent:8081/a2a/message",
    "explicador_llm": "http://explicador-llm:8082/a2a/message",
    "interfaz_llm_agent": "http://interfaz-llm:8083/a2a/message"
}

# === APLICACIÓN FASTAPI ===
app = FastAPI(title="Servidor MCP con enrutamiento A2A")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

con = duckdb.connect(DB_PATH)
con.execute("LOAD iceberg;")

# === MODELO DE MENSAJE A2A ===
class A2AMessage(BaseModel):
    from_: str
    to: str
    intent: str
    payload: Dict[str, Any]

# === ENDPOINT CENTRAL A2A ===
@app.post("/a2a/message")
async def enrutar_mensaje(message: A2AMessage):
    try:
        if message.intent == "consulta.sql":
            # Reenviar a llm_sql_agent
            return reenviar("llm_sql_agent", message)

        elif message.intent == "consulta.sql.generada":
            # Ejecutar SQL directamente sobre DuckDB
            query = message.payload.get("query")
            if not query:
                return {"error": "No SQL query provided"}

            datos = con.execute(query).fetchnumpy()
            registros = [dict(zip(datos.keys(), row)) for row in zip(*datos.values())]
            return reenviar("explicador_llm", A2AMessage(
                from_="mcp-server",
                to="explicador_llm",
                intent="consulta.sql.resultado",
                payload={"resultado": registros, "pregunta": message.payload.get("pregunta", "")}
            ))

        elif message.intent == "respuesta.natural":
            # Reenviar respuesta final al agente interfaz
            return reenviar("interfaz_llm_agent", message)

        else:
            return {"error": f"Intent no reconocido: {message.intent}"}

    except Exception as e:
        return {"error": str(e)}

# === FUNCIONES AUXILIARES ===
def reenviar(agent: str, message: A2AMessage):
    url = AGENT_ENDPOINTS.get(agent)
    if not url:
        return {"error": f"Agente '{agent}' no registrado"}
    response = requests.post(url, json=message.dict())
    return response.json()

# === METADATOS PARA LLMs (Protocolo MCP) ===
@app.get("/tool/info/productos")
def obtener_productos():
    try:
        resultado = con.execute(f"SELECT DISTINCT producto FROM {DUCKDB_CATALOG}").fetchall()
        return {"productos": [r[0] for r in resultado]}
    except Exception as e:
        return {"error": str(e)}

@app.get("/tool/info/fechas")
def obtener_rango_fechas():
    try:
        resultado = con.execute(f"SELECT MIN(fecha), MAX(fecha) FROM {DUCKDB_CATALOG}").fetchone()
        return {"min_fecha": str(resultado[0]), "max_fecha": str(resultado[1])}
    except Exception as e:
        return {"error": str(e)}

@app.get("/tool/consulta")
def ejecutar_sql_directo(sql: str):
    try:
        datos = con.execute(sql).fetchnumpy()
        registros = [dict(zip(datos.keys(), row)) for row in zip(*datos.values())]
        return {"resultado": registros}
    except Exception as e:
        return {"error": str(e)}

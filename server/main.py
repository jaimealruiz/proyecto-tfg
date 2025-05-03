from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any
import duckdb
import os

# Modelos A2A
class A2AMessage(BaseModel):
    from_: str = Field(..., alias="from")
    to: str
    intent: str
    payload: Dict[str, Any]

class A2AResponse(BaseModel):
    from_: str = Field(..., alias="from")
    to: str
    intent: str
    payload: Dict[str, Any]

# Inicialización de FastAPI
app = FastAPI(title="Servidor MCP para Apache Iceberg")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Conexión a DuckDB
DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'lake.duckdb'))
con = duckdb.connect(DB_PATH)
con.execute("LOAD iceberg;")

# Endpoints REST tradicionales
@app.get("/tool/consulta")
def ejecutar_consulta(sql: str = Query(..., description="Consulta SQL sobre el lago de datos Iceberg")):
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

# Endpoint para manejar mensajes A2A
@app.post("/a2a/message", response_model=A2AResponse)
async def manejar_a2a(message: A2AMessage):
    try:
        if message.to == "mcp_sql_agent" and message.intent == "consulta.sql":
            query = message.payload.get("query")
            if not query:
                raise ValueError("No SQL query provided in payload")

            datos = con.execute(query).fetchnumpy()
            registros = [dict(zip(datos.keys(), row)) for row in zip(*datos.values())]

            return A2AResponse(
                from_="mcp_sql_agent",
                to=message.from_,
                intent="consulta.sql.resultado",
                payload={"resultado": registros}
            )

        raise ValueError(f"Agente destino '{message.to}' o intent '{message.intent}' no reconocido")

    except Exception as e:
        return {
            "from": "mcp_sql_agent",
            "to": message.from_,
            "intent": "error",
            "payload": {"error": str(e)}
        }

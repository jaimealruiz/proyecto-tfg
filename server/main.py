from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import duckdb
import os

### uvicorn main:app --reload

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

# Ejecutar consulta SQL
@app.get("/tool/consulta")
def ejecutar_consulta(sql: str = Query(..., description="Consulta SQL sobre el lago de datos Iceberg")):
    try:
        resultado = con.execute(sql).fetchall()
        columnas = [desc[0] for desc in con.description]
        datos = [dict(zip(columnas, fila)) for fila in resultado]
        return {"resultado": datos}
    except Exception as e:
        return {"error": str(e)}

# Devolver lista de productos únicos
@app.get("/tool/info/productos")
def obtener_productos():
    try:
        resultado = con.execute("SELECT DISTINCT producto FROM iceberg_space.ventas").fetchall()
        productos = [fila[0] for fila in resultado]
        return {"productos": productos}
    except Exception as e:
        return {"error": str(e)}

# Devolver rango de fechas
@app.get("/tool/info/fechas")
def obtener_rango_fechas():
    try:
        resultado = con.execute("SELECT MIN(fecha), MAX(fecha) FROM iceberg_space.ventas").fetchone()
        return {"min_fecha": str(resultado[0]), "max_fecha": str(resultado[1])}
    except Exception as e:
        return {"error": str(e)}

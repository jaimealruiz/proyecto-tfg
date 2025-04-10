from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import sqlite3
import os

app = FastAPI(
    title="Servidor MCP",
    description="Servidor MCP para conectar LLM con base de datos vía API REST.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "datos.db"

def init_db():
    if not os.path.exists(DB_FILE):
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE conocimiento (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pregunta TEXT NOT NULL UNIQUE,
                respuesta TEXT NOT NULL
            );
        """)
        cursor.execute("""
            INSERT INTO conocimiento (pregunta, respuesta)
            VALUES (?, ?)
        """, ("¿Cuál es la capital de Francia?", "La capital de Francia es París."))
        conn.commit()
        conn.close()

init_db()

@app.get("/contexto/")
def obtener_contexto(pregunta: str = Query(...)):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT respuesta FROM conocimiento WHERE pregunta = ?", (pregunta,))
    resultado = cursor.fetchone()
    conn.close()

    if resultado:
        return {"pregunta": pregunta, "respuesta": resultado[0]}
    else:
        return {"pregunta": pregunta, "respuesta": ""}  # Devuelve respuesta vacía (sin error)

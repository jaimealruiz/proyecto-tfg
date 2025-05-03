from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import uuid
import logging

app = FastAPI(title="Agente Interfaz – A2A")

# Modelo de entrada del usuario
class PreguntaUsuario(BaseModel):
    pregunta: str

# Configurar logging opcional
logging.basicConfig(level=logging.INFO)

# Identificador único del agente
AGENTE_ID = "interfaz_llm_agent"
MCP_URL = "http://mcp-server:8000/a2a/message"

@app.post("/preguntar")
def manejar_pregunta(data: PreguntaUsuario):
    try:
        message_id = str(uuid.uuid4())
        logging.info(f"[{message_id}] Pregunta recibida del usuario: {data.pregunta}")

        # 1. Enviar pregunta al MCP para que la reenvíe a llm_sql_agent
        msg_a_sql = {
            "from_": AGENTE_ID,
            "to": "llm_sql_agent",
            "intent": "consulta.sql",
            "payload": {"pregunta": data.pregunta, "message_id": message_id}
        }
        resp_sql = requests.post(MCP_URL, json=msg_a_sql)
        sql_response = resp_sql.json()

        if "payload" not in sql_response or "query" not in sql_response["payload"]:
            raise Exception(f"Respuesta no válida del llm_sql_agent: {sql_response}")

        # 2. Enviar el SQL generado al MCP para que lo reenvíe y consulte la BD
        sql = sql_response["payload"]["query"]
        msg_consulta = {
            "from_": AGENTE_ID,
            "to": "mcp_sql_agent",
            "intent": "consulta.sql",
            "payload": {"query": sql, "message_id": message_id}
        }
        resp_bd = requests.post(MCP_URL, json=msg_consulta)
        bd_response = resp_bd.json()

        if "payload" not in bd_response or "resultado" not in bd_response["payload"]:
            raise Exception(f"Respuesta no válida del mcp_sql_agent: {bd_response}")

        # 3. Enviar resultado a explicador_llm
        resultado = bd_response["payload"]["resultado"]
        msg_a_explicador = {
            "from_": AGENTE_ID,
            "to": "explicador_llm_agent",
            "intent": "respuesta.sql",
            "payload": {
                "pregunta": data.pregunta,
                "resultado": resultado,
                "message_id": message_id
            }
        }
        resp_explicador = requests.post(MCP_URL, json=msg_a_explicador)
        explicacion = resp_explicador.json()

        if "payload" not in explicacion or "respuesta" not in explicacion["payload"]:
            raise Exception(f"Respuesta no válida del explicador_llm_agent: {explicacion}")

        return {
            "respuesta": explicacion["payload"]["respuesta"],
            "sql": sql,
            "origen_datos": resultado
        }

    except Exception as e:
        logging.error(f"[{message_id}] Error durante el flujo A2A: {e}")
        raise HTTPException(status_code=500, detail=str(e))

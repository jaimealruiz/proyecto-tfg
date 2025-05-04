from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from utils.model_utils import generar_sql, consultar_mcp, generar_respuesta, enviar_mensaje_a2a

router = APIRouter()

class ConsultaRequest(BaseModel):
    pregunta: str

@router.post("/")
def hacer_consulta(data: ConsultaRequest):
    try:
        sql = generar_sql(data.pregunta)
        datos = consultar_mcp(sql)
        if not datos:
            return {"respuesta": "No se encontró información relevante en el lago de datos."}
        respuesta = generar_respuesta(data.pregunta, datos)
        return {"sql": sql, "respuesta": respuesta}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/a2a")
def hacer_consulta_a2a(data: ConsultaRequest):
    try:
        sql = generar_sql(data.pregunta)

        mensaje_a2a = {
            "from_": "llm_agent",
            "to": "mcp_sql_agent",
            "intent": "consulta.sql",
            "payload": {"query": sql}
        }

        respuesta_mcp = enviar_mensaje_a2a(mensaje_a2a)

        if "payload" not in respuesta_mcp:
            return {"error": "No se recibió un payload válido desde el MCP"}

        return {
            "sql_generado": sql,
            "respuesta_mcp": respuesta_mcp["payload"]
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

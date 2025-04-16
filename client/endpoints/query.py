from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from utils.model_utils import generar_sql, consultar_mcp, generar_respuesta

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

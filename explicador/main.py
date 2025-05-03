from fastapi import FastAPI
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModelForCausalLM
from typing import Dict, Any
import torch
import json

app = FastAPI(title="Agente A2A: Explicador LLM")

# Carga del modelo
modelo = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
tokenizer = AutoTokenizer.from_pretrained(modelo)
model = AutoModelForCausalLM.from_pretrained(modelo, torch_dtype=torch.float32)
model.to(torch.device("cpu"))

# Modelo Pydantic para A2A
class A2AMessage(BaseModel):
    from_: str
    to: str
    intent: str
    payload: Dict[str, Any]

@app.post("/a2a/message")
def procesar_mensaje_a2a(message: A2AMessage):
    if message.to != "explicador_llm" or message.intent != "respuesta.explicacion":
        return {"error": "Intent o destinatario no válido."}

    pregunta = message.payload.get("pregunta")
    resultado = message.payload.get("resultado")
    
    if not pregunta or not resultado:
        return {"error": "Payload incompleto. Se requieren 'pregunta' y 'resultado'."}

    contexto = json.dumps(resultado, indent=2)
    prompt = f"""
Eres un asistente que explica de forma clara y resumida los resultados de una consulta a partir de los siguientes datos.

❓ Pregunta del usuario: {pregunta}
📦 Resultado de la consulta: {contexto}

🧠 Explicación:
"""
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    outputs = model.generate(**inputs, max_new_tokens=200, temperature=0.5, do_sample=True)
    explicacion = tokenizer.decode(outputs[0], skip_special_tokens=True)

    return {
        "from": "explicador_llm",
        "to": message.from_,
        "intent": "respuesta.explicacion.resultado",
        "payload": {
            "explicacion": explicacion.strip()
        }
    }

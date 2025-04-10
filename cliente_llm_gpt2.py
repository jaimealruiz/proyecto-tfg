import requests
from transformers import GPT2LMHeadModel, GPT2Tokenizer
import torch

modelo_nombre = "gpt2"
tokenizer = GPT2Tokenizer.from_pretrained(modelo_nombre)
model = GPT2LMHeadModel.from_pretrained(modelo_nombre)

device = torch.device("cpu")
model.to(device)

def obtener_contexto(pregunta: str) -> str:
    try:
        url = "http://127.0.0.1:8000/contexto/"
        response = requests.get(url, params={"pregunta": pregunta})
        if response.status_code == 200:
            return response.json().get("respuesta", "")
        else:
            return ""
    except Exception:
        return ""

while True:
    pregunta_usuario = input("\n🧠 Pregunta (o 'salir'): ")
    if pregunta_usuario.lower() == "salir":
        break

    contexto = obtener_contexto(pregunta_usuario)

    if contexto:
        prompt = f"Pregunta: {pregunta_usuario}\nContexto: {contexto}\nRespuesta:"
    else:
        prompt = f"Pregunta: {pregunta_usuario}\nRespuesta:"

    inputs = tokenizer(prompt, return_tensors="pt").to(device)

    outputs = model.generate(
        **inputs,
        max_new_tokens=50,
        do_sample=True,
        temperature=0.1
    )

    respuesta = tokenizer.decode(outputs[0], skip_special_tokens=True)
    print("\n=== RESPUESTA GENERADA ===\n")
    print(respuesta)

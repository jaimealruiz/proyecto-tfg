import requests
import json
import logging
import os

# Logging
HABILITAR_LOGS = False

if HABILITAR_LOGS:
    log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), 'logs'))
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "consulta_externa.log")
    logging.basicConfig(
        filename=log_path,
        filemode="a",
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=logging.INFO
    )

def registrar_log(mensaje):
    if HABILITAR_LOGS:
        logging.info(mensaje)

# Configuración
API_URL = "http://localhost:8080/query"

def realizar_consulta(pregunta: str):
    try:
        registrar_log(f"[Pregunta] {pregunta}")
        response = requests.post(API_URL, json={"pregunta": pregunta})
        response.raise_for_status()
        data = response.json()
        registrar_log(f"[Respuesta] {json.dumps(data, indent=2)}")
        return data.get("respuesta", "No se obtuvo respuesta.")
    except Exception as e:
        registrar_log(f"[Error] {e}")
        return f"Error al realizar la consulta: {e}"

# Interfaz de consola
if __name__ == "__main__":
    print("Cliente de prueba para interactuar con el LLM")
    while True:
        pregunta = input("\nEscribe tu pregunta (o 'salir'): ")
        if pregunta.lower() == "salir":
            break
        respuesta = realizar_consulta(pregunta)
        print(f"\nRespuesta:\n{respuesta}")

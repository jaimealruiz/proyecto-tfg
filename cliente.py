import requests
import json
import logging
import os

# Configuración
API_BASE = "http://localhost:8080"
MODOS = {
    "1": "/query",       # Tradicional: LLM genera respuesta completa
    "2": "/query/a2a"    # Interoperabilidad A2A: solo SQL, respuesta tipo agente
}

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

def realizar_consulta(pregunta: str, modo: str):
    endpoint = MODOS.get(modo)
    if not endpoint:
        return "Modo de consulta no válido."

    try:
        registrar_log(f"[Modo: {modo}] [Pregunta] {pregunta}")
        response = requests.post(f"{API_BASE}{endpoint}", json={"pregunta": pregunta})
        response.raise_for_status()
        data = response.json()
        registrar_log(f"[Respuesta] {json.dumps(data, indent=2)}")

        if modo == "1":
            return data.get("respuesta", "No se obtuvo respuesta.")
        elif modo == "2":
            payload = data.get("payload", {})
            return json.dumps(payload, indent=2)
    except Exception as e:
        registrar_log(f"[Error] {e}")
        return f"Error al realizar la consulta: {e}"

# Interfaz de consola
if __name__ == "__main__":
    print("Cliente de prueba para interactuar con el LLM\n")
    print("Selecciona el modo de consulta:")
    print("1. Modo tradicional (/query)")
    print("2. Modo A2A interoperable (/query/a2a)")

    modo = input("Introduce el número de modo [1/2]: ").strip()
    if modo not in MODOS:
        print("Modo inválido. Finalizando.")
        exit()

    while True:
        pregunta = input("\nEscribe tu pregunta (o 'salir'): ")
        if pregunta.lower() == "salir":
            break
        respuesta = realizar_consulta(pregunta, modo)
        print(f"\nRespuesta:\n{respuesta}")

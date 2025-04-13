from transformers import AutoModelForCausalLM, AutoTokenizer
import torch, requests, json, logging, os
from datetime import datetime

DEBUG = False
ENABLE_BACKUP_ANSWER = False  # En el futuro se puede activar para permitir respuestas sin datos (RAG)

# Configuración de logs
log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'logs'))
os.makedirs(log_dir, exist_ok=True)
log_path = os.path.join(log_dir, "cliente_llm.log")
logging.basicConfig(
    filename=log_path,
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# Cargar modelo
modelo = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
tokenizer = AutoTokenizer.from_pretrained(modelo)
model = AutoModelForCausalLM.from_pretrained(modelo, torch_dtype=torch.float32)
device = torch.device("cpu")
model.to(device)

def extraer_info_tabla():
    try:
        productos_resp = requests.get("http://127.0.0.1:8000/tool/info/productos")
        fechas_resp = requests.get("http://127.0.0.1:8000/tool/info/fechas")

        productos = productos_resp.json().get("productos", [])
        fechas = fechas_resp.json()
        min_fecha = fechas.get("min_fecha", "")
        max_fecha = fechas.get("max_fecha", "")
        return productos, min_fecha, max_fecha
    except Exception as e:
        logging.error(f"Error al obtener metadatos del MCP: {e}")
        return [], "", ""

def generar_sql(pregunta: str) -> str:
    productos, min_fecha, max_fecha = extraer_info_tabla()
    productos_str = ", ".join(f"'{p}'" for p in productos)

    prompt = f"""
Eres un asistente experto en SQL y tienes acceso a una única tabla llamada **iceberg_space.ventas**. Esta tabla contiene información de ventas de productos con las columnas:

- fecha (DATE)
- producto (TEXT)
- cantidad (INTEGER)
- precio (DOUBLE)

⚠️ REGLAS:
- Usa siempre **iceberg_space.ventas** (nunca 'ventas' a secas).
- Usa filtros de producto y fecha solo si son necesarios.
- No inventes columnas ni esquemas.
- El rango de fechas real es: {min_fecha} a {max_fecha}
- Los productos disponibles son: {productos_str}

Ejemplos:
❓ ¿Cuántas unidades se vendieron del producto 'Router X'?
✅ SELECT SUM(cantidad) FROM iceberg_space.ventas WHERE producto = 'Router X';

❓ ¿Cuál ha sido el ingreso total?
✅ SELECT SUM(cantidad * precio) AS ingreso_total FROM iceberg_space.ventas;

Ahora responde:
❓ {pregunta}
✅ SQL:
"""

    if DEBUG:
        print("\n📥 PROMPT PARA GENERAR SQL:")
        print(prompt)
    logging.info(f"[SQL Prompt] {pregunta}")
    logging.info(prompt)

    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    output = model.generate(**inputs, max_new_tokens=100, temperature=0.7, do_sample=True)
    respuesta = tokenizer.decode(output[0], skip_special_tokens=True)

    if "SQL:" in respuesta:
        sql_raw = respuesta.split("SQL:")[-1].strip()
    else:
        sql_raw = respuesta.strip()

    if not sql_raw.endswith(";"):
        sql_raw += ";"

    return sql_raw

def consultar_mcp(sql: str):
    try:
        response = requests.get("http://127.0.0.1:8000/tool/consulta", params={"sql": sql})
        json_data = response.json()
        if DEBUG:
            print("\n📦 RESPUESTA DEL MCP:")
            print(json.dumps(json_data, indent=2))
        logging.info(f"[MCP Respuesta] {json.dumps(json_data, indent=2)}")
        return json_data.get("resultado", [])
    except Exception as e:
        logging.error(f"Error al consultar el MCP: {e}")
        return []

def generar_respuesta(pregunta: str, datos: list) -> str:
    contexto = json.dumps(datos, indent=2)
    prompt = f"""
Eres un asistente inteligente que responde preguntas de usuarios basándose únicamente en los datos extraídos mediante una consulta SQL a un lago de datos.

🔐 No tienes acceso a ninguna otra fuente de información.

📌 Instrucciones:
- Responde en español, de forma clara y directa.
- No repitas la pregunta ni el formato del prompt.
- No inventes información.
- Si los datos están vacíos, responde educadamente que no hay datos disponibles.

❓ Pregunta del usuario:
{pregunta}

📦 Datos del lago de datos:
{contexto}

✍️ Respuesta:
"""

    if DEBUG:
        print("\n🧠 PROMPT PARA GENERAR RESPUESTA:")
        print(prompt)
    logging.info(f"[Prompt Respuesta] {prompt}")

    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    output = model.generate(**inputs, max_new_tokens=100, temperature=0.5, do_sample=True)
    respuesta = tokenizer.decode(output[0], skip_special_tokens=True)
    logging.info(f"[Respuesta generada] {respuesta}")
    return respuesta.strip()

# Bucle principal
while True:
    pregunta = input("\n🧠 Escribe tu pregunta (o 'salir'): ")
    if pregunta.lower() == "salir":
        break

    logging.info(f"\n=== Pregunta nueva: {pregunta} ===")
    sql = generar_sql(pregunta)
    print(f"\n🧾 Consulta generada: {sql}")
    datos = consultar_mcp(sql)

    if not datos:
        logging.warning("No se obtuvo información del MCP.")
        print("⚠️ No se pudo obtener información.")

        if ENABLE_BACKUP_ANSWER:
            prompt = f"""
Eres un asistente útil. El sistema no ha encontrado información relevante en la base de datos para responder a la siguiente pregunta:

❓ Pregunta: {pregunta}

Aun así, intenta dar una respuesta útil basada en tu conocimiento general.
"""
            inputs = tokenizer(prompt, return_tensors="pt").to(device)
            output = model.generate(**inputs, max_new_tokens=100, temperature=0.7, do_sample=True)
            respuesta_backup = tokenizer.decode(output[0], skip_special_tokens=True)
            print("\n=== RESPUESTA ALTERNATIVA ===\n")
            print(respuesta_backup.strip())
            logging.info(f"[Respuesta alternativa] {respuesta_backup.strip()}")

        continue

    respuesta = generar_respuesta(pregunta, datos)
    print("\n=== RESPUESTA ===\n")
    print(respuesta)

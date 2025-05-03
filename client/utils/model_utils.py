from transformers import AutoModelForCausalLM, AutoTokenizer
import torch, requests, json, logging, os

modelo = "TinyLlama/TinyLlama-1.1B-Chat-v1.0"
tokenizer = AutoTokenizer.from_pretrained(modelo)
model = AutoModelForCausalLM.from_pretrained(modelo, torch_dtype=torch.float32)
model.to(torch.device("cpu"))

log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'logs'))
os.makedirs(log_dir, exist_ok=True)
logging.basicConfig(
    filename=os.path.join(log_dir, "cliente_llm.log"),
    filemode="a",
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

def extraer_info_tabla():
    try:
        productos_resp = requests.get("http://mcp-server:8000/tool/info/productos")
        fechas_resp = requests.get("http://mcp-server:8000/tool/info/fechas")
        productos = productos_resp.json().get("productos", [])
        fechas = fechas_resp.json()
        return productos, fechas.get("min_fecha", ""), fechas.get("max_fecha", "")
    except Exception as e:
        logging.error(f"Error metadatos MCP: {e}")
        return [], "", ""

def generar_sql(pregunta: str) -> str:
    productos, min_fecha, max_fecha = extraer_info_tabla()
    productos_str = ", ".join(f"'{p}'" for p in productos)

    prompt = f"""
Eres un experto en SQL con acceso a una tabla llamada iceberg_space.ventas:
- fecha (DATE)
- producto (TEXT)
- cantidad (INTEGER)
- precio (DOUBLE)

Usa siempre iceberg_space.ventas.
Productos: {productos_str}
Fechas: {min_fecha} a {max_fecha}

❓ Pregunta: {pregunta}
✅ SQL:
"""
    logging.info(f"[SQL Prompt] {prompt}")
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    output = model.generate(**inputs, max_new_tokens=100, temperature=0.7, do_sample=True)
    respuesta = tokenizer.decode(output[0], skip_special_tokens=True)

    sql = respuesta.split("SQL:")[-1].strip()
    if not sql.endswith(";"):
        sql += ";"
    return sql

def consultar_mcp(sql: str):
    try:
        response = requests.get("http://mcp-server:8000/tool/consulta", params={"sql": sql})
        data = response.json()
        logging.info(f"[MCP Respuesta] {json.dumps(data, indent=2)}")
        return data.get("resultado", [])
    except Exception as e:
        logging.error(f"Error al consultar el MCP: {e}")
        return []

def generar_respuesta(pregunta: str, datos: list) -> str:
    contexto = json.dumps(datos, indent=2)
    prompt = f"""
Eres un asistente que responde preguntas de usuarios con datos de una consulta SQL.

❓ Pregunta: {pregunta}
📦 Datos: {contexto}

✍️ Respuesta:
"""
    logging.info(f"[Respuesta Prompt] {prompt}")
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    output = model.generate(**inputs, max_new_tokens=200, temperature=0.5, do_sample=True)
    respuesta = tokenizer.decode(output[0], skip_special_tokens=True)
    return respuesta.strip()


def enviar_mensaje_a2a(mensaje: dict):
    try:
        response = requests.post("http://mcp-server:8000/a2a/message", json=mensaje)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        logging.error(f"Error al enviar mensaje A2A: {e}")
        return {"error": str(e)}

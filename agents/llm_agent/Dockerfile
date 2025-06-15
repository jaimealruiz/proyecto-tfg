FROM python:3.11-slim

WORKDIR /app

# 1) Instalamos dependencias
RUN pip install --no-cache-dir \
        fastapi uvicorn[standard] \
        requests transformers pydantic \
    && pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir PyJWT
RUN pip install --no-cache-dir cryptography

RUN pip install --no-cache-dir httpx

# 2) Copiamos el código completo del agente
COPY server/   ./server
COPY utils/    ./utils
COPY agents/llm_agent/ ./

EXPOSE 8003

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003", "--reload", "--log-level", "debug"]

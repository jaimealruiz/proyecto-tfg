FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi uvicorn[standard] \
    requests pydantic

RUN pip install --no-cache-dir PyJWT
RUN pip install --no-cache-dir cryptography

RUN pip install --no-cache-dir httpx

# Copiamos el módulo A2A y el código del agente
COPY server/ ./server
COPY agents/ventas_agent/ ./

EXPOSE 8002

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002", "--reload", "--log-level", "debug"]

# agents/ventas_agent/Dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi uvicorn[standard] \
    requests pydantic

# Copiamos el módulo A2A y el código del agente
COPY server/ ./server
COPY agents/ventas_agent/ ./

EXPOSE 8002

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]

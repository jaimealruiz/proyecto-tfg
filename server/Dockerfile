# server/Dockerfile
FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi uvicorn[standard] \
    duckdb requests pydantic

# Copia todo el código del servidor (incluye a2a_models.py y main.py)
COPY server/ ./

# Montamos ./data en /app/data para tener lake.duckdb
VOLUME ["/app/data"]

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

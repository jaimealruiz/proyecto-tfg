FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

# Instala las dependencias (torch==2.2.2 es la versión CPU por defecto)
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "cliente_llm_api:app", "--host", "0.0.0.0", "--port", "8001"]

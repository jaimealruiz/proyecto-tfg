FROM python:3.12-slim

# Evitar prompts interactivos
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Crear directorio de trabajo
WORKDIR /app

# Instalar dependencias del sistema necesarias para duckdb y FastAPI
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias de Python
COPY server/requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copiar el código fuente del servidor
COPY server/ .

# Lanzar el servidor FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

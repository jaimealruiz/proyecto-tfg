FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    git \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copiar el resto de los archivos del microservicio
COPY . .

# Ejecutar el servidor FastAPI
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8090"]

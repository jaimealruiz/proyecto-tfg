FROM python:3.12-slim

# Evitar prompts interactivos
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Instalar Python packages
COPY client/requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copiar el código fuente del cliente
COPY client/ .

# Entrypoint por defecto (se puede sobrescribir si se desea usar interactivo)
CMD ["python", "cliente_llm.py"]

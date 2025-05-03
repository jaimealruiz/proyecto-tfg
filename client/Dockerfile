FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias del sistema
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Instalar requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copiar código
COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8081"]

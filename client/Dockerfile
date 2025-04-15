FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

# Instala pip y las dependencias base
RUN pip install --upgrade pip

# Instala las dependencias de la aplicación
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "cliente_llm.py"]

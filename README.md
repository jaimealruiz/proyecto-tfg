# Diseño e Implementación de un Lago de Datos Basado en Apache Iceberg para su Integración en una Arquitectura de Recuperación Aumentada

## Descripción del Proyecto
Este repositorio contiene la implementación de un **lago de datos** basado en **Apache Iceberg**, diseñado para garantizar transacciones ACID, versionado de datos y optimización del acceso a la información. Su finalidad es integrarse con una **arquitectura de recuperación aumentada (RAG)**, permitiendo mejorar el acceso y la fiabilidad de los datos para futuras aplicaciones de inteligencia artificial.

## Estructura del Repositorio
```
📂 proyecto-tfg
│── 📂 docs                      # Documentación del proyecto
│   ├── propuesta_tfg.pdf
│   ├── diseño_arquitectura.md
│   ├── guía_despliegue.md
│── 📂 infra                      # Configuración de infraestructura
│   ├── docker-compose.yml        # Definición de contenedores
│   ├── k8s/                      # Manifests para Kubernetes (si aplica)
│── 📂 data-lake                   # Implementación de Apache Iceberg
│   ├── setup_iceberg.py          # Configuración inicial
│   ├── ingest_data.py            # Scripts de ingesta
│   ├── queries.sql               # Consultas de prueba
│── 📂 backend                    # Backend de acceso a datos
│   ├── app/                      # Código fuente
│   ├── main.py                   # Punto de entrada
│   ├── requirements.txt          # Dependencias
│── 📂 rag                        # Arquitectura RAG
│   ├── retrieval.py              # Módulo de recuperación
│   ├── integration.py            # Integración con el modelo Deep Seek
│── 📂 tests                      # Pruebas del sistema
│   ├── test_iceberg.py
│   ├── test_retrieval.py
│── README.md                     # Descripción del proyecto
│── .gitignore                     # Archivos a ignorar en Git
```

## Tecnologías Utilizadas
- **Apache Iceberg** para la gestión del lago de datos
- **Docker y Kubernetes** para la contenedorización
- **Apache Spark, Trino o Flink** para consultas y procesamiento
- **Python** para la implementación de scripts y servicios
- **Spring Boot** en el backend
- **React** en el frontend

## Instalación y Configuración
### 1. Clonar el repositorio
```bash
git clone https://github.com/usuario/proyecto-tfg.git
cd proyecto-tfg
```
### 2. Configurar y desplegar contenedores con Docker Compose
```bash
docker-compose up -d
```
### 3. Ingestar datos en Apache Iceberg
```bash
python data-lake/ingest_data.py
```

## Documentación
La documentación completa sobre la arquitectura, despliegue y funcionamiento del sistema se encuentra en la carpeta `docs/`.

## Licencia
Licencia
Todos los derechos reservados por el autor. No se permite la distribución, modificación o uso sin consentimiento explícito.

## Contacto
jaimealru99@gmail.com

[LinkedIn](https://www.linkedin.com/in/jaimealonsoruiz/)

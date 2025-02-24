# proyecto-tfg
El proyecto consiste en la implementación de un lago de datos basado en Apache Iceberg para su integración en una arquitectura RAG con el propósito de enriquecer consultas mediante la integración de información almacenada antes de realizar inferencias con un modelo de Deep Seek.

## Estructura del proyecto
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
│── 📂 rag                        # Arquitectura RAG (diseñada por el tutor)
│   ├── retrieval.py              # Módulo de recuperación
│   ├── integration.py            # Integración con el modelo Deep Seek
│── 📂 tests                      # Pruebas del sistema
│   ├── test_iceberg.py
│   ├── test_retrieval.py
│── README.md                     # Descripción del proyecto
│── .gitignore                     # Archivos a ignorar en Git

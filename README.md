# JAR-A2A: Comunicación Multiagente Soberana con Protocolos MCP y A2A

Este repositorio contiene la implementación de un sistema de comunicación multiagente basado en modelos de lenguaje (LLM), construido como prueba de concepto del **protocolo JAR-A2A** (Any-to-Any). El sistema integra dos protocolos inspirados en la literatura reciente: **MCP (Model Context Protocol)** y **A2A**, con un diseño modular preparado para su integración futura con marcos de identidad soberana y espacios de datos federados.

## 🔍 Propósito del Proyecto

Este trabajo se enmarca en un proyecto de investigación centrado en la intersección entre:

- Comunicación entre agentes inteligentes distribuidos
- Acceso soberano a datos en entornos federados (Data Spaces)
- Estándares emergentes como **Google A2A** y **Gaia-X Trust Framework**

El objetivo principal es ofrecer una arquitectura abierta y extensible para la mensajería entre agentes autónomos, compatible con principios de interoperabilidad, trazabilidad y control de identidad.

---

## 🧱 Estructura del Sistema

El sistema se compone de tres microservicios principales:

- **LLM Agent**: Genera consultas SQL a partir de preguntas en lenguaje natural.
- **MCP Server**: Actúa como broker, registrador y pasarela de acceso a la base de datos.
- **Ventas Agent**: Ejecuta consultas SQL y devuelve resultados estructurados.
- - 🧪 **DuckDB + Apache Iceberg**: se ha utilizado un lake-house local con la tabla `iceberg_space.ventas` que contiene:
  - `fecha` (DATE)
  - `producto` (TEXT)
  - `cantidad` (INTEGER)
  - `precio` (DOUBLE)

Todos los servicios se comunican utilizando el protocolo **JAR-A2A**, que extiende el modelo de envelopes definido por Google con mecanismos de control asincrónico, retransmisión, discovery semántico y separación lógica de servicios.

---

## 🧪 Funcionalidades implementadas

- Registro dinámico de agentes y descubrimiento por capacidades
- Confirmación de entrega (ACKs) y retransmisión en caso de fallo
- Heartbeats periódicos para supervisión de disponibilidad
- Correlación de mensajes mediante `correlation_id`
- Exposición de servicios contextualizados vía protocolo MCP
- Generación automática de SQL a partir de lenguaje natural con LLM local
- Comunicación A2A entre agentes mediante mensajes JSON estructurados

---

## ⚙️ Tecnologías empleadas

- Python 3.11
- FastAPI
- Docker & Docker Compose
- DuckDB
- Apache Iceberg
- TinyLlama (modelo LLM local)
- JWT (explorado para futura integración de seguridad federada)

---

## 🚀 Despliegue local

El proyecto se despliega localmente mediante Docker Compose:

```bash
docker compose build
docker compose up
````
Para replicar las pruebas del flujo de comunicación realizadas durante la documentación del proyecto, se puede hacer uso del script cli.py:

```bash
python scripts/cli.py "Introduzca-consulta-al-LLM"
````

Asegúrate de que los puertos 8000, 8002 y 8003 estén libres. La interfaz de consulta está expuesta en el puerto 8003 bajo el endpoint /query.

## Consideraciones de seguridad

Aunque el sistema no incorpora por defecto mecanismos criptográficos, ha sido diseñado para permitir en el futuro:

- Firma de mensajes (JWT + RS256)

- Identidad descentralizada (DID + Verifiable Credentials)

- Validación de políticas de autorización y trazabilidad

  Puede consultarte la exploración a esta aproximación implementada en la rama **security**.

# Documentación del TFG: Interconexión entre Espacios de Datos e Inteligencia Artificial Generativa

**Fecha**: 11/04/2025  
**Autor**: Jaime Alonso Ruiz
**Tutor**: Joaquín Salvachúa
**Título del TFG**: *Diseño e implementación de interconexión entre espacios de datos e inteligencia artificial generativa*

---

## 🎯 Propósito del proyecto

El objetivo principal de este Trabajo de Fin de Grado es diseñar e implementar una arquitectura funcional y escalable que permita a un modelo de lenguaje (LLM) interactuar con un espacio de datos utilizando el **Model Context Protocol (MCP)**.  
El cliente (el modelo de lenguaje) **no debe acceder directamente a la base de datos**, sino que todas las operaciones deben realizarse exclusivamente a través del servidor MCP, que actúa como capa intermedia segura, modular y extensible.

---

## 🧱 Arquitectura actual

### Componentes principales:

- **🧠 Cliente LLM (`cliente_llm.py`)**
  - Ejecuta preguntas en lenguaje natural.
  - Utiliza el modelo `TinyLlama-1.1B-Chat-v1.0`.
  - Genera consultas SQL a partir de preguntas.
  - Consulta datos exclusivamente a través del servidor MCP.
  - Interpreta los resultados devueltos y construye una respuesta explicativa.
  - Registra todo el proceso en un log: `logs/cliente_llm.log`.

- **🔗 Servidor MCP (`main.py`)**
  - Desarrollado en FastAPI.
  - Conectado a un espacio de datos local basado en DuckDB.
  - Exposición de herramientas MCP mediante endpoints REST:
    - `/tool/consulta`: ejecuta una consulta SQL.
    - `/tool/info/productos`: devuelve la lista de productos distintos.
    - `/tool/info/fechas`: devuelve el rango mínimo y máximo de fechas registradas.

- **📂 Espacio de datos**
  - Implementado localmente usando DuckDB (`lake.duckdb`).
  - Contiene una tabla `iceberg_space.ventas` con las siguientes columnas:
    - `fecha` (DATE)
    - `producto` (TEXT)
    - `cantidad` (INTEGER)
    - `precio` (DOUBLE)
  - Los datos se cargan desde `load_data.py`.

---

## 🔒 Principios y decisiones clave

- ✅ Separación estricta entre procesamiento semántico (LLM) y acceso a datos (MCP).
- ✅ Cumplimiento del diseño propuesto por MCP: los LLMs acceden a los datos solo a través de herramientas ("tools").
- ✅ Uso de prompts enriquecidos con información contextual previa obtenida del MCP.
- ✅ Arquitectura modular, extensible y trazable mediante logs.

---

## 📈 Escalabilidad futura

El diseño actual se ha planteado desde el principio con una visión clara de crecimiento:

- 🔁 Sustitución futura de DuckDB por Apache Iceberg real o incluso Trino/Presto.
- 🤖 Sustitución del modelo TinyLlama por un LLM más avanzado o alojado en GPU.
- 🔎 Evolución hacia una arquitectura RAG (Retrieval-Augmented Generation), donde:
  - El LLM consulta primero un vector store basado en embeddings generados desde el MCP.
  - El contenido recuperado se pasa como contexto al modelo para respuestas más precisas.

Además, se podrán incorporar nuevas herramientas MCP como:

- `/tool/info/esquema`
- `/tool/info/documentacion`
- `/tool/descargar`
- `/tool/upload-pdf`

---

## 📜 Conclusión

Se ha establecido una base sólida, funcional y alineada con las exigencias del TFG.  
El sistema ya permite una interacción completa entre un modelo de lenguaje y un espacio de datos, cumpliendo con los principios del MCP y dejando preparado el camino para su futura evolución hacia un sistema RAG más avanzado.


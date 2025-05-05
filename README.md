# Documentación del TFG: Interconexión entre Espacios de Datos e Inteligencia Artificial Generativa

**Fecha**: 11/04/2025  
**Autor**: Jaime Alonso Ruiz
**Tutor**: Joaquín Salvachúa
**Título del TFG**: *Diseño e implementación de interconexión entre espacios de datos e inteligencia artificial generativa*

---

## Propósito del proyecto

El objetivo principal de este Trabajo de Fin de Grado es diseñar e implementar una arquitectura funcional y escalable que permita a un sistema multiagente (LLMs) interactuar entre sí mediante un **protocolo estandarizado** basado en el **Google A2A (Agent to Agent)**, y con un espacio de datos utilizando el **Model Context Protocol (MCP)**.  
Los agentes **no deben interactuar directamente entre sí ni acceder directamente a la base de datos**, sino que todas las operaciones deben realizarse exclusivamente a través del Broker A2A-MCP, que actúa como Hub intermediario, seguro, modular y extensible.

---

## Infraestructura actual

Se ha desplegado una infraestructura de contenedores basada en **Docker Compose** que incluye:

o	**Un servidor MCP** que actúa como broker de mensajes A2A.

o	**Un agente LLM** que genera consultas **SQ**L a partir de preguntas en **lenguaje natural**.

o	**Un agente** de ventas que **ejecuta las consultas** SQL sobre una base de datos en formato Iceberg y **responde con los resultados**.

•	Cada componente ha sido diseñado de forma modular e independiente, con **interfaces REST** expuestas mediante **FastAPI**.

•	Se ha utilizado **DuckDB** como motor de consultas para el backend en esta primera fase local.

- **Espacio de datos**
  - Implementado localmente usando DuckDB (`lake.duckdb`).
  - Contiene una tabla `iceberg_space.ventas` con las siguientes columnas:
    - `fecha` (DATE)
    - `producto` (TEXT)
    - `cantidad` (INTEGER)
    - `precio` (DOUBLE)
  - Los datos se cargan desde `load_data.py`.

---

## Protocolo de comunicación A2A
- Se ha definido un protocolo de mensajes A2A basado en objetos JSON que siguen un esquema tipo:

>  
  
    {
    
      "message_id": "uuid",
    
	    "sender": "agent_id",
   
	    "recipient": "agent_id",
   
	    "timestamp": "ISO8601",
   
	    "type": "query" | "response",
   
	    "body": {...}
   
	  }
- El MCP almacena un registro en memoria de los agentes registrados, incluyendo su agent_id y su URL de callback.
- Los agentes se registran al inicio mediante un mensaje POST /agent/register. El agent_id puede ser fijo o generado aleatoriamente por el MCP si no se especifica.
- El agente LLM actúa como iniciador de las consultas, enviando mensajes query al agente de ventas.
- El agente de ventas responde con un mensaje response, incluyendo el resultado y un correlation_id para que el LLM pueda completar la consulta.

---

## Agente LLM
- Se ha integrado el modelo de lenguaje TinyLlama (TinyLlama-1.1B-Chat-v1.0) de forma local usando transformers, para evitar dependencias externas.
-	El agente LLM genera prompts contextualizados con metadatos obtenidos del MCP (productos y fechas disponibles), mediante el Modern Context Protocol (MCP), para generar SQL válido.
-	También es responsable de convertir los resultados en lenguaje natural mediante un segundo prompt.
-	El agente soporta un endpoint /query que acepta preguntas en lenguaje natural y coordina todo el ciclo de consulta y respuesta

---

## Identificadores fijos y configuración
-	Se han fijado los agent_id de ambos agentes mediante un fichero .env, y se ha corregido la configuración para que el contenedor ventas-agent lo importe correctamente.
-	Se han introducido mejoras de robustez como:
-	Esperas iniciales para resolución DNS y arranque del MCP.
-	Retransmisiones exponenciales en caso de fallo de registro.
-	Registro de logs detallado en cada componente.

---

## Cliente de consola
Se ha creado un script CLI que permite interactuar con el sistema desde la terminal, enviando preguntas al LLM-Agent y mostrando en consola el SQL generado y la respuesta.

---

## Principios y decisiones clave

- Separación estricta entre procesamiento semántico (LLM) y acceso a datos (MCP).
- Cumplimiento del diseño propuesto por MCP: los LLMs acceden a los datos solo a través de herramientas ("tools").
- Uso de prompts enriquecidos con información contextual previa obtenida del MCP.
- Cumplimiento de las especificaciones publicadas del Google A2A.
- Arquitectura modular, extensible y trazable mediante logs.

---

## Plan de Trabajo Futuro

- **Verificación funcional completa:** Realizar pruebas de extremo a extremo entre el cliente CLI, el LLM-Agent, el broker MCP y el agente de ventas.
- **Extensión al protocolo Google A2A:** Adoptar elementos clave de la especificación Google A2A, incluyendo:
  - Identidad estructurada y metadatos del agente (Agent Card).
  - Soporte opcional de JSON-RPC 2.0.
  - Canal de eventos unidireccional (eventos push) con Server-Sent Events (SSE).

- **Persistencia y auditoría:**
  - Extensión del MCP para registrar mensajes y agentes en una base de datos (SQLite o PostgreSQL)..
  - Incorporación de IDs de conversación para trazabilidad.
 
- **Documentación y despliegue local reproducible:**
  - Redacción de README técnico con instrucciones paso a paso.
  - Scripts automáticos de puesta en marcha y pruebas.

## Conclusión provisional

Hasta la fecha, se ha implementado de forma satisfactoria una arquitectura funcional basada en agentes cooperantes que utilizan lenguaje natural y SQL para consultar datos sobre un formato Iceberg. Se ha verificado la comunicación mediante un broker A2A minimalista, y el sistema ha demostrado ser modular, escalable y ampliable hacia futuros estándares de interoperabilidad como Google A2A.


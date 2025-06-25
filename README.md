# JAR-A2A (Branch: security) — Comunicación Multiagente con Seguridad Criptográfica

Esta rama del repositorio incorpora una versión extendida del sistema JAR-A2A con **firma digital de mensajes A2A** utilizando JWT con claves RSA-2048 (RS256). Supone una evolución natural de la arquitectura definida en la rama principal, orientada a su uso en entornos federados con requisitos de **autenticación, integridad y trazabilidad**.

---

## 🔐 Características de Seguridad

- 📜 **Mensajes firmados con JWT RS256**
  - Cada mensaje A2A se firma con la clave privada del agente emisor.
  - El broker (MCP) valida la firma mediante la clave pública correspondiente.
- 🧾 **Validación del campo `aud` (audience)**
  - Se garantiza que los mensajes van dirigidos al broker correcto.
- 🧠 **Emisor lógico como `iss`**
  - El campo `iss` representa el nombre lógico del agente (`llm_agent`, `ventas_agent`, etc.), no el `agent_id` dinámico.

---

## 🔧 Requisitos adicionales

- Las claves RSA deben estar ubicadas y montadas en contenedores vía volumen:
	- /secrets/private.pem # Clave privada del agente
	- /secrets/public_keys/ # Directorio con las claves públicas de todos los agentes


- Variables de entorno necesarias en cada servicio:
- `PRIVATE_KEY_PATH`
- `PUBLIC_KEYS_DIR`
- `BROKER_ID` (nombre lógico del MCP, usado como audience esperada)

---

## 🧱 Arquitectura

El sistema sigue el mismo esquema multiagente de la rama principal, con las siguientes diferencias clave:

- Todos los mensajes A2A enviados al broker (MCP) están firmados.
- El broker valida la firma y reconstruye el `Envelope` o `Jar`.
- Se han adaptado los agentes para incluir campos `iss` y `aud` correctamente.

---

## 🧪 Estado del sistema

✔️ Funcionalidades activas:

- Registro, discovery y heartbeats verificados con JWT
- Retransmisión con ACKs firmados
- Generación de consultas por LLM y ejecución distribuida
- Validación de `aud` y `iss` por parte del broker

⚠️ Funcionalidades aún no implementadas:

- Firma de respuestas devueltas por el broker
- Rotación y gestión automatizada de claves
- Identidad federada mediante DID + VC

---

## 🛠️ Despliegue

```bash
docker compose -f docker-compose.yml --env-file .env up --build
```

Ejemplo de variables necesarias en .env:

BROKER_ID=mcp-server
PRIVATE_KEY_PATH=/secrets/private.pem
PUBLIC_KEYS_DIR=/secrets/public_keys
LLM_AGENT_ID=...
VENTAS_AGENT_ID=...

## 📄 Archivos clave
- security/security.py: Firma y verificación de tokens JWT.

- main.py (agentes): Firma de heartbeats, ACKs y mensajes A2A.

- server/main.py: Verificación y reenvío de JWT firmados.

## 🧭 Consideraciones
Esta rama constituye una prueba de concepto de seguridad para el protocolo JAR-A2A, y servirá de base para la integración futura con identidad soberana (SSI) y mecanismos de confianza federada. Se recomienda consultar la rama principal para la versión estable sin seguridad criptográfica.

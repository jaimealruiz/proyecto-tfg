# Rama `mcp-Iceberg` – Implementación inicial del lago de datos local

Esta rama recoge la primera fase funcional del proyecto, en la que se diseñó e implementó un **lago de datos local** basado en Apache Iceberg utilizando **DuckDB como motor de consultas**. Su objetivo principal fue validar el protocolo MCP para acceso estructurado a datos en lenguaje natural, sirviendo como base del desarrollo posterior orientado a agentes A2A.

---

## 📌 Objetivos principales de esta rama

- Implementar un **servidor MCP** que sirviera de interfaz única para los modelos LLM, gestionando consultas y metadatos.
- Crear un **lago de datos local** usando Iceberg y DuckDB.
- Exponer endpoints REST para:
  - Ejecutar consultas SQL.
  - Obtener metainformación (productos disponibles, rango de fechas).
- Cargar datos en formato CSV de forma reproducible para pruebas.


---

## 🔁 Flujo general del sistema

1. Los datos de ventas se almacenan en archivos `.csv` dentro de `/data/csv`.
2. El script `load_data.py` carga esos datos en una tabla Iceberg.
3. El servidor MCP expone endpoints para:
   - Realizar consultas SQL (`/tool/consulta`)
   - Obtener metadatos de productos (`/tool/info/productos`)
   - Obtener rangos de fechas (`/tool/info/fechas`)
4. DuckDB accede al catálogo Iceberg y ejecuta las consultas solicitadas.

---

## 🧠 Características clave

- 📦 **Catálogo Iceberg local**: Se gestiona en `/data/warehouse`, accesible desde el contenedor.
- ✅ **Versión sin Hive**: Se optó por el catálogo tipo `HadoopTables` para simplificar el despliegue.
- 🧪 **Modo desarrollo habilitado**: Uso de `unsafe_enable_version_guessing = true` para facilitar pruebas.
- 🔌 **FastAPI con CORS habilitado** para permitir acceso desde otros servicios LLM.

---

## 🚀 Despliegue y uso

### 1. Construir e iniciar los servicios

```bash
docker-compose up --build
```
### 2. Insertar datos
```bash
docker-compose exec mcp-server python /app/load_data.py
```

### 3. Consultar el lago de datos

- Obtener productos:
```bash
GET http://localhost:8000/tool/info/productos
```

- Obtener fechas:
```bash
GET http://localhost:8000/tool/info/productos
```

- Realizar consulta SQL:
```bash
GET http://localhost:8000/tool/consulta?sql=SELECT+COUNT(*)+FROM+iceberg_scan('/data/warehouse/ventas')
```

Esta rama fue utilizada para validar que el protocolo MCP pudiera actuar como punto central entre LLMs y el lago de datos, estableciendo las bases para la posterior arquitectura distribuida basada en agentes A2A.

Las rutas están adaptadas al sistema de archivos del contenedor, asegurando compatibilidad entre WSL2 y Docker.

## ⚠️ Notas
- Esta rama fue utilizada para validar que el protocolo MCP pudiera actuar como punto central entre LLMs y el lago de datos, estableciendo las bases para la posterior arquitectura distribuida basada en agentes A2A.

- Las rutas están adaptadas al sistema de archivos del contenedor, asegurando compatibilidad entre WSL2 y Docker.



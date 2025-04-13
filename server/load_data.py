import duckdb

con = duckdb.connect("../data/lake.duckdb")
con.execute("LOAD iceberg;")

# Crear tabla local (no usar 'USING iceberg')
con.execute("""
CREATE SCHEMA IF NOT EXISTS iceberg_space;

CREATE TABLE IF NOT EXISTS iceberg_space.ventas (
    fecha DATE,
    producto TEXT,
    cantidad INTEGER,
    precio DOUBLE
);
""")

con.execute("""
INSERT INTO iceberg_space.ventas VALUES
    ('2024-04-01', 'Router X', 10, 120.0),
    ('2024-04-01', 'Switch Y', 5, 85.5),
    ('2024-04-02', 'Router X', 7, 120.0),
    ('2024-04-03', 'Switch Y', 2, 85.5),
    ('2024-04-03', 'Firewall Z', 3, 300.0);
""")

print("✅ Datos de ejemplo insertados.")

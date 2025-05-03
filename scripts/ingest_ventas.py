from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, IntegerType, StringType, DoubleType, DateType

# Crear sesión Spark con configuración Iceberg
spark = (
    SparkSession.builder
    .appName("Ingestar CSV en Iceberg")
    .config("spark.sql.catalog.local", "org.apache.iceberg.spark.SparkCatalog")
    .config("spark.sql.catalog.local.type", "hadoop")
    .config("spark.sql.catalog.local.warehouse", "./data/warehouse")
    .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
    .config("spark.jars", "/opt/iceberg/iceberg.jar")
    .getOrCreate()
)

# Esquema de la tabla
schema = StructType([
    StructField("id", IntegerType(), True),
    StructField("producto", StringType(), True),
    StructField("cantidad", IntegerType(), True),
    StructField("precio", DoubleType(), True),
    StructField("fecha", DateType(), True),
])

# Ruta del CSV
csv_path = "/data/csv/ventas_2024-04.csv"

# Leer CSV e insertar en tabla Iceberg
df = spark.read.option("header", True).schema(schema).csv(csv_path)

# Crear tabla si no existe
df.writeTo("local.ventas").using("iceberg").createOrReplace()

spark.stop()


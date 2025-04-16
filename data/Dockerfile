FROM alpine:3.18

# Crear directorio de datos y establecerlo como volumen
RUN mkdir -p /data
WORKDIR /data

# Esto permite que otros contenedores lo usen como volumen compartido
VOLUME /data

# No hay proceso principal; este contenedor solo actúa como volumen persistente
CMD ["sleep", "infinity"]

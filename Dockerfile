# Usamos la imagen solicitada
FROM debian:trixie-slim

# Evitar prompts interactivos durante la instalación
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Instalación de dependencias del sistema
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    python3-venv \
    libpq5 \
    libpq-dev \
    gcc \
    apache2 \
    libapache2-mod-wsgi-py3 \
    postgresql-client \
    pkg-config \
    && apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Crear y activar entorno virtual (Recomendado en Debian moderno para evitar conflictos)
RUN python3 -m venv /env
ENV PATH="/env/bin:$PATH"

WORKDIR /app

# Instalar dependencias de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copiar el código del proyecto
COPY ./src /app/
# COPY ./lilex.conf /etc/apache2/sites-available/000-default.conf

# Copiar el script de automatización a la raíz del contenedor
# COPY ./entrypoint.sh /entrypoint.sh
# Darle permisos de ejecución dentro del entorno Linux de Debian
# RUN chmod +x /entrypoint.sh

EXPOSE 8000

# ENTRYPOINT ["/entrypoint.sh"]
CMD ["apachectl", "-D", "FOREGROUND"]
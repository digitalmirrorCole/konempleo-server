FROM python:3.11-slim

# Evita buffering de logs
ENV PYTHONUNBUFFERED=1

WORKDIR /konempleo
COPY ./requirements.txt /konempleo/requirements.txt

# Instala dependencias del sistema necesarias
RUN apt-get update && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    libtesseract-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# Instala dependencias Python
RUN pip install --upgrade pip && pip install --no-cache-dir -r /konempleo/requirements.txt

# Copia el resto del código
COPY . /konempleo/

# Expone el puerto de la app
EXPOSE 8000

# Variables por defecto (App Runner puede sobrescribir)
ENV PORT=8000 APP_ENV=production

# Da permisos al script
RUN chmod +x /konempleo/docker-start.sh

# Comando de arranque
CMD ["/konempleo/docker-start.sh"]

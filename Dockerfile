FROM python:3.8

WORKDIR /konempleo
COPY ./requirements.txt /konempleo/requirements.txt

# Install dependencies
RUN apt-get update && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    libtesseract-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir -r /konempleo/requirements.txt

# Copy the application code
COPY . /konempleo/

# Copy the .env file
COPY ./app/.env /konempleo/app/.env
COPY ./app/.env /konempleo/migrations/.env
COPY ./app/.env /konempleo/db/.env

# Set environment variable from .env file
ENV $(cat /konempleo/app/.env)

EXPOSE 8000

COPY docker-start.sh /konempleo/docker-start.sh
RUN chmod +x /konempleo/docker-start.sh

# Command to run the application
CMD [ "/konempleo/docker-start.sh" ]

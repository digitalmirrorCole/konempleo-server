FROM python:3.8

WORKDIR /konempleo
COPY ./requirements.txt /konempleo/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r /konempleo/requirements.txt

# Copy the application code
COPY . /konempleo/

# Copy the .env file
COPY ./app/.env /konempleo/app/.env
COPY ./app/.env /konempleo/migrations/.env
COPY ./app/.env /konempleo/db/.env

# Set environment variable from .env file
ENV $(cat /konempleo/app/.env)

EXPOSE 80

# Command to run the application
CMD [ "docker-start.sh" ]

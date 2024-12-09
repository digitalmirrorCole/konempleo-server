FROM python:3.8

WORKDIR /konempleo
COPY ./requirements.txt /konempleo/requirements.txt

# Install dependencies
RUN pip install --no-cache-dir -r /konempleo/requirements.txt

# Copy the application code
COPY ./app /konempleo/app
COPY ./db /konempleo/db
COPY ./migrations /konempleo/migrations
COPY ./migrations/versions /konempleo/migrations/versions
COPY ./models /konempleo/models
COPY ./alembic.ini /konempleo/alembic.ini
COPY ./README.md /konempleo/README.md

# Copy the .env file
COPY ./app/.env /konempleo/app/.env
COPY ./app/.env /konempleo/migrations/.env
COPY ./app/.env /konempleo/db/.env

# Set environment variable from .env file
ENV $(cat /konempleo/app/.env)

# Run Alembic migration
CMD [ "alembic", "upgrade", "head" ]
# RUN alembic upgrade head

# Command to run the application
CMD [ "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "80" ]

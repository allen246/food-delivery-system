FROM python:3.10.12-alpine

# Set unbuffered output for python
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Create app directory
WORKDIR /app

# Install app dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Bundle app source
COPY .. .

# Expose port
EXPOSE 8000

RUN chmod +x scripts/django.sh
RUN chmod +x scripts/worker-entrypoint.sh
# entrypoint to run the django.sh file
# ENTRYPOINT ["scripts/django.sh"]
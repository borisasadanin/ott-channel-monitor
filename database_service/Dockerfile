FROM python:3.10

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Installera curl för healthcheck
RUN apt-get update && apt-get install -y curl

COPY . .

# Sätt miljövariabel för att förhindra att Python buffrar output
ENV PYTHONUNBUFFERED=1

# Använd CMD istället för ENTRYPOINT för att köra Flask-appen
CMD ["python", "-u", "database.py"]
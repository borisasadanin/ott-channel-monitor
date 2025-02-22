FROM python:3.10-slim

WORKDIR /app

# Ställ in Python så att det inte buffrar loggar
ENV PYTHONUNBUFFERED=1

# Kopiera och installera beroenden
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Kopiera resten av koden
COPY . .

# Kör tjänsten
#CMD ["python", "-m", "monitor_service.monitor"]

CMD ["python", "monitor.py"]



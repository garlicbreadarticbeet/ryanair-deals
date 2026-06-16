# Image voor worker / bot / web (Hetzner-deploy via docker-compose).
# Python 3.12 matcht de CI/handoff-versie.
FROM python:3.12-slim

WORKDIR /app

# Dependencies eerst (betere layer-cache).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default; per service overschreven in docker-compose.yml.
CMD ["python", "-m", "app.worker", "run"]

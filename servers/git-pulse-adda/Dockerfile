FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY metrics.py server.py ./

# Run as an unprivileged user
RUN useradd --create-home --uid 10001 app
USER app

ENV PORT=8080
EXPOSE 8080

CMD ["python", "server.py"]

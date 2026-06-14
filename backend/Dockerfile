FROM python:3.12-slim

# espeak-ng: offline TTS voices for pyttsx3
# ffmpeg: audio decoding for Whisper transcription
# libpq-dev + gcc: build psycopg2 if no wheel is available for the platform
RUN apt-get update && apt-get install -y --no-install-recommends \
    espeak-ng \
    ffmpeg \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

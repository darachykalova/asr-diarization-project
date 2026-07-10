FROM asr-app
# Reuse the base image (already has torch, numpy, sqlalchemy, minio, celery).
# Vosk + pyyaml are added via requirements.txt rebuild of asr-app, so no extra pip here.
WORKDIR /app
EXPOSE 8100
CMD ["uvicorn", "call_agent.main:app", "--host", "0.0.0.0", "--port", "8100"]

FROM python:3.12-slim
WORKDIR /app
COPY backend/delivery/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/domain /app/backend/domain
COPY backend/delivery /app/backend/delivery
COPY genai/harpia /app/genai/harpia
ENV PYTHONPATH=/app/backend:/app/backend/domain:/app/genai
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "delivery.app:build_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]

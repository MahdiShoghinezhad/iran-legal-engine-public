FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir .
ENV LEGAL_DB=/app/storage/demo.sqlite3
RUN mkdir -p /app/storage
EXPOSE 8000
CMD ["uvicorn", "legalcore.api:app", "--host", "0.0.0.0", "--port", "8000"]

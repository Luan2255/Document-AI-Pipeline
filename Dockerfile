# Install the OCR engine and language data in a small Python runtime image.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-por \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install the package before dropping privileges for runtime execution.
COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir . \
    && useradd --create-home --shell /usr/sbin/nologin appuser

USER appuser
EXPOSE 8000

# Run the API with a single worker; scale through container replicas.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
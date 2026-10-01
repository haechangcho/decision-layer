FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

# dependencies first so code edits don't bust the layer cache
COPY pyproject.toml README.md LICENSE ./
RUN mkdir -p src/decision_layer && touch src/decision_layer/__init__.py && pip install -e .
COPY src/ src/

EXPOSE 8000
CMD ["uvicorn", "decision_layer.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

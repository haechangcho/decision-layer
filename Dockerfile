FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
ARG DL_PYTHON_EXTRAS=""

# Native runtime needed only by optional statistical libraries.
RUN if [ -n "$DL_PYTHON_EXTRAS" ]; then apt-get update && apt-get install -y --no-install-recommends libgomp1 && rm -rf /var/lib/apt/lists/*; fi

# dependencies first so code edits don't bust the layer cache
COPY pyproject.toml README.md LICENSE ./
RUN mkdir -p src/decision_layer && touch src/decision_layer/__init__.py && \
    if [ -n "$DL_PYTHON_EXTRAS" ]; then \
      apt-get update && apt-get install -y --no-install-recommends build-essential && \
      pip install -e ".[$DL_PYTHON_EXTRAS]" && \
      apt-get purge -y --auto-remove build-essential && rm -rf /var/lib/apt/lists/*; \
    else pip install -e .; fi
COPY src/ src/

EXPOSE 8000
CMD ["uvicorn", "decision_layer.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

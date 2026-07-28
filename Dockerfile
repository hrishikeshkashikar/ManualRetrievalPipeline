# ══════════════════════════════════════════════════════════════════════════
#  Machine Manual RAG — Self-Contained Docker Image
#  Builds a fully offline, plug-and-play image with ALL models baked in:
#    • Ollama runtime + vision model (qwen2.5vl:7b by default)
#    • BAAI/bge-base-en-v1.5  (embedding)
#    • BAAI/bge-reranker-v2-m3 (reranker)
#
#  Usage:
#    docker build --build-arg VISION_MODEL=qwen2.5vl:7b -t manual-rag:latest .
#    docker compose up -d
# ══════════════════════════════════════════════════════════════════════════

# ── Build args (override via --build-arg) ──────────────────────────────────
ARG VISION_MODEL=qwen2.5vl:3b
ARG EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
ARG RERANKER_MODEL=BAAI/bge-reranker-v2-m3
ARG PYTHON_VERSION=3.11

# ══════════════════════════════════════════════════════════════════════════
# STAGE 1 — Pull Ollama vision model
#   Uses the official Ollama image to pull the model blobs into /root/.ollama
#   These blobs are later copied into the final runtime image.
# ══════════════════════════════════════════════════════════════════════════
FROM ollama/ollama:latest AS model-downloader

ARG VISION_MODEL

# Start Ollama, pull the vision model, then export binary/libs/blobs for runtime
RUN ollama serve & \
    OLLAMA_PID=$! && \
    echo "Waiting for Ollama to start..." && \
    sleep 8 && \
    echo "Pulling vision model: ${VISION_MODEL}" && \
    ollama pull "${VISION_MODEL}" && \
    echo "Model pull complete. Shutting down Ollama..." && \
    kill $OLLAMA_PID && \
    wait $OLLAMA_PID 2>/dev/null || true && \
    mkdir -p /export/usr/bin /export/usr/lib && \
    cp /usr/bin/ollama /export/usr/bin/ollama && \
    if [ -d /usr/lib/ollama ]; then cp -a /usr/lib/ollama /export/usr/lib/; \
    else mkdir -p /export/usr/lib/ollama; fi && \
    cp -a /root/.ollama /export/ollama-home

# ══════════════════════════════════════════════════════════════════════════
# STAGE 2 — Download HuggingFace models
#   Downloads embedding + reranker models from HuggingFace into /opt/hf_models
#   so the final image can run fully offline (HF_HUB_OFFLINE=1).
# ══════════════════════════════════════════════════════════════════════════
FROM python:${PYTHON_VERSION}-slim AS hf-downloader

ARG EMBEDDING_MODEL
ARG RERANKER_MODEL

# Minimal system deps for torch/transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install only what's needed to download models
RUN pip install --no-cache-dir \
    sentence-transformers>=3.0.0 \
    torch>=2.2.0

ENV HF_HOME=/opt/hf_models

# Write Python download scripts to files first (avoids Docker mis-parsing
# "from sentence_transformers import ..." as a FROM instruction)
RUN printf '%s\n' \
    'import os' \
    'from sentence_transformers import SentenceTransformer' \
    'model_name = os.environ["EMBEDDING_MODEL"]' \
    'print(f"Downloading embedding model: {model_name}")' \
    'model = SentenceTransformer(model_name)' \
    'dim = model.get_sentence_embedding_dimension()' \
    'print(f"Embedding model ready — dimension: {dim}")' \
    > /tmp/download_embedding.py

RUN printf '%s\n' \
    'import os' \
    'from sentence_transformers import CrossEncoder' \
    'model_name = os.environ["RERANKER_MODEL"]' \
    'print(f"Downloading reranker model: {model_name}")' \
    'model = CrossEncoder(model_name)' \
    'print("Reranker model ready")' \
    > /tmp/download_reranker.py

# Download embedding model
RUN EMBEDDING_MODEL="${EMBEDDING_MODEL}" python /tmp/download_embedding.py

# Download reranker model
RUN RERANKER_MODEL="${RERANKER_MODEL}" python /tmp/download_reranker.py


# ══════════════════════════════════════════════════════════════════════════
# STAGE 3 — Runtime image (final)
#   • Inherits from python:3.11-slim
#   • Copies Ollama binary + model blobs from stage 1
#   • Copies HuggingFace models from stage 2
#   • Installs app dependencies
#   • Uses supervisord to run ollama serve + uvicorn side-by-side
# ══════════════════════════════════════════════════════════════════════════
FROM python:${PYTHON_VERSION}-slim AS runtime

ARG VISION_MODEL
ARG EMBEDDING_MODEL
ARG RERANKER_MODEL

# ── System dependencies ───────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    supervisor \
    zstd \
    && rm -rf /var/lib/apt/lists/*

# ── Install Ollama binary & libraries (exported from stage 1) ─────────────
COPY --from=model-downloader /export/usr/bin/ollama /usr/bin/ollama
COPY --from=model-downloader /export/usr/lib/ollama /usr/lib/ollama

# ── Copy baked-in Ollama model blobs ─────────────────────────────────────
COPY --from=model-downloader /export/ollama-home /root/.ollama

# ── Copy baked-in HuggingFace models ─────────────────────────────────────
COPY --from=hf-downloader /opt/hf_models /opt/hf_models

# ── Python application dependencies ──────────────────────────────────────
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ──────────────────────────────────────────────────────
COPY app/ ./app/
COPY frontend/ ./frontend/

# ── Supervisor configuration ──────────────────────────────────────────────
COPY supervisord.conf /etc/supervisor/conf.d/manual-rag.conf

# ── Entrypoint script ─────────────────────────────────────────────────────
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# ── Default data directories (overridden by volume mounts at runtime) ─────
RUN mkdir -p /app/data/chroma_db /app/data/images /app/data/manuals /kb

# ── Bake-time labels ─────────────────────────────────────────────────────
LABEL org.opencontainers.image.title="Manual RAG Pipeline" \
      org.opencontainers.image.description="Fully offline multimodal RAG for machine manuals" \
      org.opencontainers.image.version="1.0.0" \
      manual-rag.vision-model="${VISION_MODEL}" \
      manual-rag.embedding-model="${EMBEDDING_MODEL}" \
      manual-rag.reranker-model="${RERANKER_MODEL}"

# ── Environment — force offline model loading ─────────────────────────────
ENV HF_HOME=/opt/hf_models \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    MANUAL_RAG_IN_DOCKER=1 \
    OLLAMA_MODELS=/root/.ollama/models \
    OLLAMA_BASE_URL=http://127.0.0.1:11434 \
    OLLAMA_VISION_MODEL=${VISION_MODEL} \
    EMBEDDING_MODEL_NAME=${EMBEDDING_MODEL} \
    RERANKER_MODEL_NAME=${RERANKER_MODEL} \
    DATA_DIR=/app/data \
    CHROMA_PERSIST_DIR=/app/data/chroma_db \
    IMAGE_STORE_DIR=/app/data/images \
    MANUAL_STORE_DIR=/app/data/manuals \
    HOST=0.0.0.0 \
    PORT=8000

# ── Expose ports ──────────────────────────────────────────────────────────
EXPOSE 8000
EXPOSE 11434

ENTRYPOINT ["/entrypoint.sh"]

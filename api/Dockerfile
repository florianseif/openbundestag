# HF Space (Docker SDK) image for the OpenBundestag JSON API.
# In the Space repo this Dockerfile sits at the root next to api/ and src/.
FROM python:3.12-slim

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface \
    # The 2 GB DuckDB file is pulled once from this public Dataset on first run.
    HF_DB_REPO=MissionJupiter/openbundestag-db \
    HF_DB_FILE=openbundestag-data.db \
    DB_PATH=openbundestag-data.db \
    # Comma-separated allowed origins (the Cloudflare Pages site). "*" for dev.
    ALLOWED_ORIGINS=* \
    PYTHONUNBUFFERED=1

RUN useradd -m -u 1000 user
USER user
WORKDIR /home/user/app

COPY --chown=user api/requirements.txt ./api/requirements.txt
RUN pip install --no-cache-dir -r api/requirements.txt

# Copies the Space repo: Dockerfile, README, api/ and the shared src/queries.py.
COPY --chown=user . .

EXPOSE 7860
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "7860"]

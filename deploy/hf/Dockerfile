FROM python:3.12-slim

# Writable home for Streamlit config + the huggingface_hub download cache.
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    HF_HOME=/home/user/.cache/huggingface \
    # Where the app fetches the 2 GB DuckDB file from on first run.
    HF_DB_REPO=MissionJupiter/openbundestag-db \
    HF_DB_FILE=openbundestag-data.db \
    # Streamlit must bind to the port HF Spaces health-checks (7860), headless.
    STREAMLIT_SERVER_PORT=7860 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

RUN useradd -m -u 1000 user
USER user
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=user . .

EXPOSE 7860
CMD ["streamlit", "run", "app.py"]

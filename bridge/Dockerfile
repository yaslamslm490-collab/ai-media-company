FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8123 \
    BRIDGE_DB_PATH=/data/manus_bridge.sqlite3

WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt \
    && useradd --create-home --uid 10001 bridge \
    && mkdir -p /data \
    && chown bridge:bridge /data
COPY bridge /app/bridge
USER bridge
EXPOSE 8123
CMD ["python", "-m", "bridge.server"]

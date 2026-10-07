FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=3000 \
    REQUIRE_DATABASE_URL=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates ffmpeg \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --uid 10001 --create-home --home-dir /home/app app

WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN python3 -m pip install --no-cache-dir --disable-pip-version-check -r requirements.txt

COPY --chown=app:app backend ./backend
COPY --chown=app:app frontend ./frontend
COPY --chown=app:app scripts/build.py ./scripts/build.py
COPY --chown=app:app index.html styles.css manus-routes.json app.js ./
RUN python3 scripts/build.py \
    && chown -R app:app /app

USER app
EXPOSE 3000
CMD ["python3", "-m", "backend.server"]

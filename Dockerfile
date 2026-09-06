FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 VERIFIER_DATA_DIR=/data VERIFIER_DISABLE_WEB_SETUP=1
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY pyproject.toml README.md ./
COPY verifier ./verifier
RUN pip install --no-cache-dir --no-deps . && useradd --uid 10001 --create-home verifier && mkdir /data && chown verifier:verifier /data
USER verifier
VOLUME /data
EXPOSE 8791
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8791/healthz',timeout=3)"
CMD ["claim-verifier","serve","--host","0.0.0.0","--port","8791","--data-dir","/data"]

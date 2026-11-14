FROM golang:1.23-alpine AS go_source
WORKDIR /build
COPY go.mod go.sum ./
RUN go mod download
COPY backend/cmd/ ./backend/cmd/
COPY backend/internal/ ./backend/internal/
COPY backend/rpc/ ./backend/rpc/
COPY database/ ./database/

FROM go_source AS go_check
RUN go vet ./...

FROM go_check AS go_build
RUN CGO_ENABLED=0 go build -trimpath -o /out/erp-site ./backend/cmd/erp

FROM python:3.11-alpine3.22 AS python_build
# 固定版 PyMuPDF 沒有 musllinux wheel，保留原版本並在建置階段編譯。
RUN test "$(uname -m)" = x86_64 \
    && apk add --no-cache build-base linux-headers swig cmake ninja pkgconf
WORKDIR /build
COPY requirements.txt ./
RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.11-alpine3.22 AS app_base
LABEL org.opencontainers.image.authors="dog0830430@gmail.com"
ENV WEB_HOST=0.0.0.0 \
    WEB_PORT=8080 \
    ERP_PYTHON=/app/.venv/bin/python \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8
RUN apk add --no-cache bash ca-certificates libstdc++ libgcc \
    libreoffice-writer tesseract-ocr tesseract-ocr-data-eng tesseract-ocr-data-chi_tra
WORKDIR /app
COPY requirements.txt ./
COPY --from=python_build /wheels /wheels
RUN python -m venv /app/.venv \
    && /app/.venv/bin/python -m pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && /app/.venv/bin/python -m pip check \
    && rm -rf /wheels
COPY backend/src/ ./backend/src/
COPY backend/__init__.py ./backend/__init__.py

FROM app_base AS runtime
COPY --from=go_build /out/erp-site ./bin/erp-site
COPY page/ ./page/
COPY start.sh ./start.sh
RUN sed -i 's/\r$//' start.sh \
    && chmod 755 start.sh bin/erp-site \
    && mkdir -p data page/static/staff \
    && bash start.sh --check
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD /app/.venv/bin/python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/api/health', timeout=5).close()"
ENTRYPOINT ["/bin/bash", "/app/start.sh"]
CMD []

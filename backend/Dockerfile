# api 이미지(컨텍스트: backend/). 빌드는 infra/docker/build_images.sh, 설계는 docs/dev-guide.html 16장.
# 비밀(.env*)은 이미지에 넣지 않는다. 서버가 /app/.env 로 읽기 전용 mount 한다.
# 베이스 이미지는 태그와 digest를 함께 고정한다(2026-11-02 Docker Hub / ghcr.io 레지스트리 조회). 올릴 때 둘을 함께 바꾼다.

ARG PYTHON_IMAGE=python:3.14.10-slim-trixie@sha256:3cabfd7d7aaf394e6040e79fa1eec6ca1c52b74ed9188650472695d9a9326999

FROM ${PYTHON_IMAGE} AS builder
# uv는 builder 스테이지에만 둔다(uv.lock을 만든 버전과 같게 고정)
COPY --from=ghcr.io/astral-sh/uv:0.10.4@sha256:4cac394b6b72846f8a85a7a0e577c6d61d4e17fe2ccee65d9451a8b3c9efb4ac /uv /uvx /bin/
ENV UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
WORKDIR /app
# 잠금 파일만 먼저 복사해 의존성 층을 캐시한다
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

FROM ${PYTHON_IMAGE} AS runtime
ARG RELEASE_TAG=unknown
LABEL org.opencontainers.image.title="neoine-sales-api" \
      org.opencontainers.image.revision="${RELEASE_TAG}"
ENV PATH="/app/.venv/bin:${PATH}" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1
RUN groupadd --gid 10001 neoine \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin neoine
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
# alembic.ini 의 script_location 이 %(here)s/alembic 이라 이 위치에서 동작한다
COPY alembic /app/alembic
COPY alembic.ini /app/alembic.ini
# compose 가 호스트 neoine 의 UID/GID 로 덮어써서 실행하므로 파일은 누구나 읽을 수 있어야 한다
USER 10001:10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

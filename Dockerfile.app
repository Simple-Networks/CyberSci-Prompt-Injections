# Build the venv with uv (the repo is uv-managed: uv.lock is tracked, .python-version is
# 3.14). The non-slim builder image carries a toolchain, so a dependency without a cp314
# wheel can still build from sdist; only the finished venv reaches the runtime image.
FROM ghcr.io/astral-sh/uv:python3.14-bookworm@sha256:73868e084ba4de5da1f7fb3c0cfa29edf93e1d965f9a1afe9a496fd6f97db574 AS builder

WORKDIR /srv
COPY pyproject.toml uv.lock ./
# pyproject.toml has no [build-system], so this installs dependencies only.
RUN uv sync --frozen --no-install-project

FROM python:3.14-slim-bookworm@sha256:9ab8d9c8514b44f90cf0029dd42fdd7e9e211e639c8b995304cc04568dee900f  

WORKDIR /srv
COPY --from=builder /srv/.venv /srv/.venv
# Unbuffered stdout matters here: the lab asks students to watch the server log for the
# tool calls the model makes.
ENV PATH="/srv/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

COPY main.py ./
COPY app ./app
COPY users.txt ./

EXPOSE 8000
CMD ["python", "main.py"]

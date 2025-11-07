ARG PYTHON_VERSION=3.13

FROM python:${PYTHON_VERSION}-slim AS build

ARG UV_BUILD_ARG="--no-dev"

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app

COPY ./uv.lock uv.lock
COPY ./pyproject.toml pyproject.toml

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync \
        --locked \
        --no-install-project \
        ${UV_BUILD_ARG}

WORKDIR /app
COPY ./src .

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync \
        --locked \
        --no-editable \
        ${UV_BUILD_ARG}


##########################################################################
FROM python:${PYTHON_VERSION}-slim


# Optional: add the application virtualenv to search path.
ENV PATH=/app/bin:$PATH


RUN <<EOT
groupadd -r nonroot -g 1000
useradd -r -u 1000 -d /app -g nonroot -N nonroot
EOT


STOPSIGNAL SIGINT

# Copy the pre-built `/app` directory to the runtime container
COPY --from=build /app /app


#USER nonroot
WORKDIR /app

EXPOSE 8000

COPY ./entrypoint.sh /

# Run the application.
CMD ["sh", "/entrypoint.sh"]

ARG PYTHON_VERSION=3.13

FROM python:${PYTHON_VERSION}-slim AS build


COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/app

COPY ./uv.lock uv.lock
COPY ./pyproject.toml pyproject.toml

RUN --mount=type=cache,target=/root/.cache \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync \
        --locked \
        --no-install-project \
        --dev

WORKDIR /app
COPY ./src .

RUN --mount=type=cache,target=/root/.cache \
    uv sync \
        --locked \
        --no-editable \
        --dev


##########################################################################
FROM python:${PYTHON_VERSION}-slim


# Optional: add the application virtualenv to search path.
ENV PATH=/app/bin:$PATH


#RUN <<EOT
#groupadd -r ildar -g 1000
#useradd -r -u 1000 -d /app -g ildar -N ildar
#EOT


STOPSIGNAL SIGINT


#RUN <<EOT
#apt-get update -qy
#apt-get install -qyy \
#    -o APT::Install-Recommends=false \
#    -o APT::Install-Suggests=false \
#    sqlite3 \
#    pydevd-pycharm
#
#apt-get clean
#rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
#EOT

# Copy the pre-built `/app` directory to the runtime container
COPY --from=build /app /app

COPY . /app/



#USER ildar
WORKDIR /app

EXPOSE 8000

# Run the application.
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

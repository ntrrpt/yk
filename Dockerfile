FROM ghcr.io/astral-sh/uv:python3.13-alpine

# uv envs
ENV UV_NO_PROGRESS=1
ENV UV_COMPILE_BYTECODE=1
ENV NO_COLOR=1
ENV UV_NO_DEV=1

# yk envs
ARG FORCE_UV_SYNC_ON_START=NAH
ENV YK_OUTPUT=/out
ENV YK_LOG=/out
ENV YK_APPRISE=/apprise
ENV YK_SRC=/src
ENV YK_COOKIES=/cookies.txt

RUN apk update
RUN apk add --no-cache --progress shadow go git ffmpeg build-base linux-headers curl

RUN git clone https://github.com/Kethsar/ytarchive.git /tmp/ytarchive
RUN go build -C /tmp/ytarchive -o /usr/local/bin/ytarchive -v

RUN mkdir -p /.cache && chmod 777 /.cache
RUN mkdir -p /yk && chmod 777 /yk

WORKDIR /yk
COPY pyproject.toml uv.lock /yk

RUN if [ "${FORCE_UV_SYNC_ON_START}" != "YES" ]; then \
        uv sync; \
    fi

COPY . /yk

ENTRYPOINT ["uv", "run", "yk.py"]
CMD []
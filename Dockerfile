FROM ghcr.io/astral-sh/uv:python3.13-alpine

ARG FORCE_UV_SYNC_ON_START=NAH
ENV UV_NO_PROGRESS=1
ENV UV_COMPILE_BYTECODE=1
ENV NO_COLOR=1
ENV YK_OUTPUT=/out

RUN apk update
RUN apk add --no-cache --progress shadow go git ffmpeg build-base linux-headers

RUN git clone https://github.com/Kethsar/ytarchive.git /tmp/ytarchive
RUN go build -C /tmp/ytarchive -o /usr/local/bin/ytarchive -v

RUN mkdir -p /.cache && chmod 777 /.cache
RUN mkdir -p /app && chmod 777 /app

WORKDIR /app
COPY . /app

RUN if [ "${FORCE_UV_SYNC_ON_START}" != "YES" ]; then \
        uv sync; \
    fi

ENTRYPOINT ["uv", "run", "yk.py"]
CMD []
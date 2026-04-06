# ytarchive
FROM golang:alpine AS ytarchive_builder
WORKDIR /yta

RUN apk add --no-cache --progress git
RUN git clone --revision=742674da1fa618365074de714b9517cc79d1bb38 https://github.com/dreammu/ytarchive /yta/git
RUN go build -C /yta/git -ldflags="-s -w" -o /yta/bin -v


# yk .venv
FROM python:3.13-alpine AS yk_builder
WORKDIR /yk

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apk add --no-cache --progress build-base linux-headers git

ENV UV_TOOL_DIR=/yk/.tools \
    UV_COMPILE_BYTECODE=1 \
    UV_NO_PROGRESS=1 \
    UV_NO_SYNC=1 \
    UV_NO_DEV=1 \
    NO_COLOR=1

RUN uv tool install yt-dlp[default]
RUN uv tool install streamlink

COPY pyproject.toml uv.lock .
RUN uv sync


# final app
FROM python:3.13-alpine
WORKDIR /yk

RUN apk add --no-cache --progress deno bash curl ffmpeg gosu

COPY --from=ytarchive_builder /yta/bin /usr/local/bin/ytarchive
COPY --from=yk_builder /yk /yk
COPY . .

RUN ln -s /yk/.tools/streamlink/bin/streamlink /usr/local/bin/streamlink 
RUN ln -s /yk/.tools/yt-dlp/bin/yt-dlp /usr/local/bin/yt-dlp 

ENV PATH="/yk/.venv/bin:$PATH" \
    YK_COOKIES=/cookies.txt \
    YK_APPRISE=/apprise.yml \
    YK_INPUT=/lists \
    YK_OUTPUT=/out \
    YK_LOG=/out

ENTRYPOINT ["./entryway.sh"]
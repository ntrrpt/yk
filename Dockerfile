# ytarchive
FROM golang:alpine AS ytarchive_builder
WORKDIR /yta

RUN apk add --no-cache --progress git
RUN git clone --revision=742674da1fa618365074de714b9517cc79d1bb38 https://github.com/dreammu/ytarchive /yta/git
RUN go build -C /yta/git -ldflags="-s -w" -o /yta/bin -v

# .venv & tools
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
RUN uv tool install git+https://github.com/ntrrpt/chat-downloader@db0ea8ca1759ecbb8390288c4d9adc4849d139b6 --with pysocks

COPY pyproject.toml uv.lock .
RUN uv sync

# final img
FROM python:3.13-alpine AS yk
WORKDIR /yk

RUN apk add --no-cache --progress deno bash curl ffmpeg gosu

COPY --from=ytarchive_builder /yta/bin /usr/local/bin/ytarchive
COPY --from=yk_builder /yk /yk
COPY . .

RUN <<-EOT sh
	ln -s /yk/.tools/chat-downloader/bin/chat_downloader /usr/local/bin/chat_downloader
	ln -s /yk/.tools/streamlink/bin/streamlink /usr/local/bin/streamlink 
	ln -s /yk/.tools/yt-dlp/bin/yt-dlp /usr/local/bin/yt-dlp
    touch /cookies.txt /apprise.yml /list.toml
    mkdir /out /.cache
EOT

ENV PATH="/yk/.venv/bin:$PATH" \
    YK_COOKIES=/cookies.txt \
    YK_APPRISE=/apprise.yml \
    YK_OUTPUT=/out \
    YK_LOG=/out

ENTRYPOINT ["./entryway.sh"]
FROM ghcr.io/astral-sh/uv:python3.13-alpine

# uv envs
ENV UV_COMPILE_BYTECODE=1
ENV UV_NO_PROGRESS=1
ENV UV_NO_DEV=1
ENV NO_COLOR=1

# yk envs
ENV YK_COOKIES=/cookies.txt
ENV YK_APPRISE=/apprise
ENV YK_OUTPUT=/out
ENV YK_LOG=/out
ENV YK_SRC=/src

RUN apk add --no-cache --progress deno bash go git curl ffmpeg build-base linux-headers 

RUN bash -c 'git clone https://github.com/Kethsar/ytarchive.git /tmp/ytarchive \
    && go build -C /tmp/ytarchive -o /usr/local/bin/ytarchive -v \
    && rm -rf /tmp/ytarchive /root/go /root/.cache/go-build'

RUN bash -c 'mkdir -p /app \ 
    && chmod -R 777 /app \
    && mkdir -p /.cache \
    && chmod 777 /.cache'

WORKDIR /app
COPY pyproject.toml uv.lock /app
RUN uv sync
COPY . /app

ENTRYPOINT ["uv", "run", "--no-sync", "yk.py"]

FROM ghcr.io/astral-sh/uv:python3.13-alpine

ENV UV_NO_PROGRESS=1
ENV NO_COLOR=1

ARG FORCE_UV_SYNC_ON_BUILD=NAH
ENV YK_OUTPUT=/out

ARG PUID=1000
ARG PGID=1000
ARG UNAME=yk


RUN apk update
RUN apk add --no-cache --progress shadow go git ffmpeg build-base linux-headers

RUN git clone https://github.com/Kethsar/ytarchive.git /tmp/ytarchive
RUN go build -C /tmp/ytarchive -o /usr/local/bin/ytarchive -v

RUN groupadd -g ${PGID} -o ${UNAME}
RUN useradd -m -u ${PUID} -g ${PGID} -o -s /bin/bash ${UNAME}
USER ${UNAME}

WORKDIR /app
COPY . /app

RUN if [ "${FORCE_UV_SYNC_ON_BUILD}" = "YES" ]; then \
        uv sync; \
    fi

ENTRYPOINT ["uv", "run", "yk.py"]
CMD []
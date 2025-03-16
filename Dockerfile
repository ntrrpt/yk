FROM ghcr.io/astral-sh/uv:python3.11-alpine

RUN apk update
RUN apk add --progress go git ffmpeg build-base linux-headers

WORKDIR /app
COPY . /app

# --no-cache
ARG DUMMY=unknown
RUN DUMMY=${DUMMY} echo

RUN git clone https://github.com/Kethsar/ytarchive.git /app/ytarchive
RUN go build -C /app/ytarchive -o /usr/local/bin/ytarchive -v

RUN uv sync

ENTRYPOINT ["uv", "run", "yk.py", "--output", "/out"]
#CMD ["sh"]
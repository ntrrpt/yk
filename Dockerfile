FROM python:3.12-alpine

RUN apk update
RUN apk add ffmpeg go git build-base linux-headers curl
RUN pip install poetry

WORKDIR /app
RUN mkdir -p /out

RUN poetry config virtualenvs.create true
COPY pyproject.toml poetry.lock* /app/
RUN poetry update --no-dev

RUN git clone https://github.com/Kethsar/ytarchive.git /app/ytarchive
RUN cd /app/ytarchive && go build -o /usr/local/bin/ytarchive

COPY . /app

ENTRYPOINT ["poetry", "run", "python", "yk.py", "--output", "/out"]
#CMD ["sh"]
FROM python:3.12-alpine

WORKDIR /app
RUN mkdir -p /out

RUN apk update
RUN apk add go gcc ffmpeg git linux-headers

RUN git clone https://github.com/Kethsar/ytarchive.git /app/ytarchive
RUN go build -C /app/ytarchive -o /usr/local/bin/ytarchive -v

RUN pip install poetry
RUN poetry config virtualenvs.create true
COPY . /app

ARG DUMMY=unknown
RUN DUMMY=${DUMMY} poetry update

ENTRYPOINT ["poetry", "run", "python", "yk.py", "--output", "/out"]
#CMD ["sh"]
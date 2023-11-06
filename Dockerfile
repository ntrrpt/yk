FROM python:3.11-rc

MAINTAINER ntrrpt

# install python and poetry
ENV PYTHONFAULTHANDLER=1 \
  PYTHONDONTWRITEBYTECOD=1 \
  PYTHONUNBUFFERED=1 \
  PYTHONHASHSEED=random \
  PIP_NO_CACHE_DIR=off \
  PIP_DISABLE_PIP_VERSION_CHECK=on \
  PIP_DEFAULT_TIMEOUT=100 \
  POETRY_VERSION=1.6.1

RUN pip install "poetry==$POETRY_VERSION"

# create application directory
WORKDIR /yk
COPY pyproject.* .
COPY *.sh .

# install deps
# RUN poetry config virtualenvs.create false
RUN poetry update --no-interaction --no-ansi

# install binaries
RUN bash -c './get_ytarchive.sh'
RUN bash -c './get_ffmpeg.sh'
RUN chmod +x ffmpeg

COPY . /yk

ENTRYPOINT [ "poetry", "run", "python", "main.py", "--output", "/tmp" ]


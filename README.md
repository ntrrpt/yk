## Poetry usage
```
curl -sSL https://install.python-poetry.org | python3 -
git clone https://github.com/ntrrpt/yakayaka.git && cd yakayaka
poetry update
poetry run python main.py --yta
```

## Docker usage
```
# log file must exist before the docker starts
touch log.txt

docker build https://github.com/ntrrpt/yakayaka.git -t yakayaka

docker run --rm -d \
  -v "$(pwd)"/log.txt:/yk/log.txt \
  -v "$(pwd)"/list.txt:/yk/list.txt \
  -v $PWD:/tmp \
  yakayaka
  --ntfy=<ntfy_id> \
  --delay=20 \
  --yta
```

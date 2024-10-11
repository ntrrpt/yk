## Poetry usage
```
pipx install poetry
git clone https://github.com/ntrrpt/yakayaka.git && cd yakayaka
poetry update
poetry run python main.py --yta
```

## Docker usage
```
docker build https://github.com/ntrrpt/yakayaka.git -t yk
```
```
docker run --rm -it \
  -v $PWD:/out \
  -v tw_list.txt:/app/list.txt \
  yk --delay=15 --ntfy=test_channel
```
```
docker run -d --restart unless-stopped \
  --net=host \
  --env HTTP_PROXY="http://127.0.0.1:10809" \
  --env HTTPS_PROXY="http://127.0.0.1:10809" \
  -v $PWD:/out \
  -v yt_list.txt:/app/list.txt \
  yk --yta --delay=30
```

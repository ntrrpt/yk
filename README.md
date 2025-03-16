## uv usage
```
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/ntrrpt/yakayaka.git && cd yakayaka
uv run yk.py --yta
```

## Docker usage
```
docker build https://github.com/ntrrpt/yakayaka.git -t yk
```
```
docker run --rm -it \
  -v $PWD:/out \
  -v $PWD/list.txt:/app/list.txt \
  yk --delay=15 --ntfy=test_channel
```
```
docker run -d --restart unless-stopped \
  --net=host \
  --env HTTP_PROXY="http://127.0.0.1:10809" \
  --env HTTPS_PROXY="http://127.0.0.1:10809" \
  -v $PWD:/out \
  -v $PWD/list.txt:/app/list.txt \
  yk --yta --delay=30
```

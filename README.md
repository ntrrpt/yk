## via uv:
```
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/ntrrpt/yk.git && cd yk
uv run yk.py -v -d 15 -s list-tw.txt
```

## via docker compose:
```
docker compose up --build
```

## via docker:

```
docker build -t yk:latest \
  --build-arg PGID=1000 \
  --build-arg PUID=1000 \
  --build-arg FORCE_UV_SYNC_ON_START=YES \
  https://github.com/ntrrpt/yk.git
```

```
docker run -d \
  --name yk \
  --restart unless-stopped \
  --network host \
  -t -i \
  -e YK_LOG_PATH=/tmp/log \
  -e YK_DELAY=15 \
  -e YK_SRC_LISTS=/tmp/list-tw.txt \
  -v "$(pwd):/out" \
  -v "$(pwd)/list-tw.txt:/tmp/list-tw.txt" \
  -v "$(pwd):/tmp/log" \
  yk:latest
```


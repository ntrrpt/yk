## via uv:
```
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/ntrrpt/yk.git && cd yk
uv run yk.py -v -d 15 -s lists/tw.txt
```

## via docker compose:
```
docker compose up --build
```

## via docker:

```
docker build -t yk:latest \
  --build-arg FORCE_UV_SYNC_ON_START=YES \
  https://github.com/ntrrpt/yk.git
```


```
docker run -d \
  --name yk \
  --restart unless-stopped \
  --network host \
  -t -i \
  -e YK_DELAY=15 \
  -v "$(pwd):/out" \
  -v "$(pwd)/lists/tw.txt:/src/tw.txt" \
  yk:latest
```


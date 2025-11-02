## via uv:
```
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/ntrrpt/yk.git && cd yk
uv run yk.py -v -d 15 -s lists/tw.toml
```

## via docker compose:
```
docker compose up --build
```

## via docker:

```
docker build -t yk:latest https://github.com/ntrrpt/yk.git
```


```
docker run -d \
  --name yk \
  --restart unless-stopped \
  --network host \
  -t -i \
  -e YK_DELAY=15 \
  -v "$(pwd):/out" \
  -v "$(pwd)/lists/tw.toml:/src/tw.toml" \
  yk:latest
```


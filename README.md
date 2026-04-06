## via uv:
```
curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/ntrrpt/yk.git && cd yk
uv run -m yk -d 30 -- https://www.twitch.tv/ironmouse
```

## via docker compose:
```
docker compose up --build
```

## via docker:

```
docker build -t yk https://github.com/ntrrpt/yk.git
```


```
docker run -d -t -i \
  --name yk \
  --restart unless-stopped \
  -e YK_DELAY=15 \
  -v "$(pwd):/out" \
  -v "$(pwd)/lists/tw.toml:/list.toml" \
  yk -i /list.toml
```


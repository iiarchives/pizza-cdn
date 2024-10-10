# Microservices / Pizza CDN

A microservice for hosting cover art from music players (Feishin, etc.) to display via Discord RPC.

### Installation

```sh
uv pip install -e .
```

### Launching

```sh
DOMAIN=coverart.example.com uv run uvicorn pizza:app
```

Set the `DOMAIN` environment variable to whatever you want the links to display.

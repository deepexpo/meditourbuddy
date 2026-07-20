# MCP Backend

A minimal FastAPI backend that connects to an MCP server and exposes its
tools over a plain REST API — so both an iOS app and a future web app can
call the same endpoints with the same auth.

```
iOS app  ┐
         ├─► FastAPI backend (this repo) ─► MCP server(s)
Web app  ┘        (JWT auth, CORS)
```

## Why this shape

- **One backend, any client.** iOS and web both just call REST endpoints
  and send a Bearer token — no client needs to know MCP exists.
- **Secrets stay server-side.** API keys / MCP credentials never ship
  inside a mobile app binary.
- **Swappable MCP layer.** `app/mcp_client.py` is the only file that knows
  about MCP. Point it at a different server, or multiple servers, without
  touching your auth or route code.
- **Scaling.** Stateless except for the long-lived MCP connection opened
  at startup (`app/main.py` lifespan). Run multiple instances behind a
  load balancer once you need more throughput (see below).

## Project layout

```
mcp-backend/
  app/
    main.py         FastAPI app, routes
    auth.py         JWT issuing/verification (demo user for now)
    mcp_client.py   MCP session lifecycle + list_tools/call_tool
    config.py       Settings from .env
    models.py       Request bodies
  example_mcp_server.py   Demo MCP server (get_time, add_numbers, echo)
  requirements.txt
  Dockerfile
  .env.example
```

## Run locally

```bash
cd mcp-backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit JWT_SECRET, DEMO_PASSWORD, etc.
uvicorn app.main:app --reload
```

Try it:

```bash
# 1. Log in
curl -X POST localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"<DEMO_PASSWORD from .env>"}'
# -> {"access_token": "...", "token_type": "bearer"}

# 2. List tools
curl localhost:8000/mcp/tools -H "Authorization: Bearer <token>"

# 3. Call a tool
curl -X POST localhost:8000/mcp/call \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"name":"add_numbers","arguments":{"a":2,"b":3}}'
```

## Connecting your real MCP server

`example_mcp_server.py` is a stand-in so the project runs immediately.
To point at your real server:

- **Local process (stdio):** set `MCP_SERVER_COMMAND` / `MCP_SERVER_ARGS`
  in `.env` to whatever launches your server.
- **Remote server (HTTP/SSE):** in `app/mcp_client.py`, replace the
  `stdio_client(...)` call with the SDK's streamable-HTTP client. Nothing
  else in the app needs to change.
- **Multiple servers:** keep a `dict[str, ClientSession]` in
  `MCPClientManager` instead of one `self.session`, and pass a server name
  through the request.

## Calling this from iOS

Standard `URLSession` calls — this is just JSON over HTTPS:

```swift
var request = URLRequest(url: URL(string: "https://your-api.com/mcp/call")!)
request.httpMethod = "POST"
request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
request.setValue("application/json", forHTTPHeaderField: "Content-Type")
request.httpBody = try JSONEncoder().encode(["name": "add_numbers", "arguments": ["a": 2, "b": 3]])
```

A future web app calls the exact same endpoints with `fetch`/`axios`, using
the CORS origin you set in `ALLOWED_ORIGINS`.

## Deploying

**Recommended: [Fly.io](https://fly.io)** — Docker-based, supports
long-running processes (needed since the MCP connection is held open),
cheap for a single small instance, and easy to scale to multiple machines
behind its built-in load balancer later.

```bash
fly launch          # detects the Dockerfile
fly secrets set JWT_SECRET=... DEMO_PASSWORD=...
fly deploy
```

Railway or Render work the same way if you prefer them (both build
straight from the Dockerfile). Avoid pure serverless/functions platforms
(Vercel functions, AWS Lambda) for the MCP layer — they kill idle
processes, which fights with holding an MCP connection open; use them
only if you switch to opening a fresh short-lived MCP connection per
request instead.

## Security checklist before going live

- Replace `authenticate_user` in `app/auth.py` with a real user store
  (hashed passwords, e.g. `passlib`) — the demo user is for local testing
  only.
- Set a strong random `JWT_SECRET` (`openssl rand -hex 32`) via your
  host's secrets manager, never commit `.env`.
- Restrict `ALLOWED_ORIGINS` to your actual web app domain(s).
- Terminate HTTPS in front of this app (Fly/Railway do this for you).
- If your MCP server itself needs credentials (API keys to a third-party
  service), keep those in backend-only env vars — never send them to the
  client.

## Scaling notes

This process holds one MCP session open for its lifetime. To scale
horizontally:
- Run N instances of this container behind a load balancer (Fly.io does
  this natively via `fly scale count N`).
- If tool calls are slow/blocking, consider a connection pool of MCP
  sessions per instance instead of a single shared one.
- Add caching (e.g. Redis) in front of `list_tools()` if it's called
  often and rarely changes.

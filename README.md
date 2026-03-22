# RummikubSolve

An optimal Rummikub move solver — tells you exactly which tiles to play and how to rearrange the board to maximize tiles placed from your rack.

## Architecture

| Layer    | Technology                                  |
|----------|---------------------------------------------|
| Frontend | Next.js 15, React 19, Tailwind CSS, Zustand |
| Backend  | FastAPI, Python 3.12+, Pydantic v2          |
| Solver   | HiGHS ILP (`highspy`), Python formulation   |
| CI/CD    | GitHub Actions                              |
| Deploy   | Docker Compose + nginx reverse proxy          |

## Repository Structure

```
backend/   FastAPI service + ILP solver (Python)
frontend/  Next.js PWA (TypeScript)
```

## Getting Started

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
uvicorn api.main:app --reload --port 8000
# → GET http://localhost:8000/health
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SENTRY_DSN` | *(empty)* | Sentry DSN; leave empty to disable error reporting |
| `ENVIRONMENT` | `development` | Controls log format (`development` → colored console, `production` → JSON) |
| `ALLOWED_ORIGIN` | `*` | CORS allowed origin — set to your frontend URL in production |
| `NEXT_PUBLIC_API_URL` | `""` (Docker) / `http://localhost:8000` (local) | Backend API base URL baked into the frontend bundle; leave empty when using nginx reverse proxy |

Copy `.env.example` to `.env` and fill in values before running.

## Running Tests

### Backend unit + integration tests

```bash
cd backend
pip install -e ".[dev]"
pytest -v
```

### E2E tests (requires backend running on :8000)

```bash
# Terminal 1
cd backend && uvicorn api.main:app --port 8000

# Terminal 2
cd frontend
npm install
npx playwright install chromium
npx playwright test
```

## Docker

### Full stack

```bash
docker compose up --build
# nginx    → http://localhost      (all traffic via reverse proxy)
# Frontend → http://localhost:3000 (direct, development only)
# Backend  → http://localhost:8000 (direct, development only)
```

### Override env vars

```bash
SENTRY_DSN=https://... ENVIRONMENT=production docker compose up
```

## Home Server Deployment

The Docker Compose setup includes an **nginx reverse proxy** that exposes a single entry point on port 80, making it suitable for home-server deployment behind a VPN.

### How it works

```
Browser → nginx:80 → /api/* → backend:8000
                   → /*     → frontend:3000
```

The frontend uses relative URLs (`/api/solve`) so it works regardless of the server's IP address or hostname — no hardcoded URLs to change.

### Steps

```bash
# 1. Clone the repo on your server
git clone https://github.com/jonasyr/RummikubSolve
cd RummikubSolve

# 2. Create your env file
cp .env.example .env
# Edit .env — set ENVIRONMENT=production; add SENTRY_DSN if wanted

# 3. Start (containers restart automatically on reboot)
docker compose up -d --build

# 4. Verify
curl http://localhost/health
# {"status":"ok","version":"0.13.0"}
```

Open `http://<server-ip>` in your browser (or `http://<tailscale-hostname>` if using Tailscale).

### Optional: HTTPS

For HTTPS without a public domain, two easy options:

- **Tailscale + HTTPS cert:** Enable HTTPS in Tailscale admin → free TLS cert for your machine's `*.ts.net` hostname, no port forwarding needed.
- **Cloudflare Tunnel:** Run `cloudflared tunnel` alongside Docker Compose to get a public HTTPS URL for free.

## Development Status

See [CHANGELOG.md](./CHANGELOG.md) for full version history.
See [Blueprint.md](./Blueprint.md) for the design document.

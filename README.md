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

## Puzzle Pool & Calibration Workflow

The backend supports an **offline puzzle pool** (SQLite) plus **telemetry export/calibration tooling** for tuning difficulty over time.

### 1) Pre-generate puzzles into the SQLite pool

The API serves `expert`/`nightmare` from the pool first (then falls back to live generation if exhausted), so pre-filling the DB improves latency for hard tiers.

```bash
cd backend
pip install -e ".[dev]"

# Generate 50 expert puzzles with 6 workers
python -m solver.generator.pregenerate --difficulty expert --count 50 --workers 6

# Generate all hard+ tiers (hard, expert, nightmare)
python -m solver.generator.pregenerate --all --count 100 --workers 4

# Inspect current pool sizes
python -m solver.generator.pregenerate --stats
```

Default DB path is `data/puzzles.db`. Override with `PUZZLE_DB_PATH` if needed:

```bash
PUZZLE_DB_PATH=/absolute/path/puzzles.db python -m solver.generator.pregenerate --stats
```

### 2) Collect telemetry from play sessions

Frontend play-mode events are written to `telemetry_events` via `POST /api/telemetry`.  
These rows are stored in the same SQLite DB path (`PUZZLE_DB_PATH`) used by the backend stores.

### 3) Export telemetry to CSV (for spreadsheet/notebook analysis)

```bash
cd backend

# Export only solved attempts from a specific calibration batch
python -m solver.generator.export_telemetry \
  --out data/telemetry_solved.csv \
  --batch-name phase6_v1 \
  --solved-only

# Export all telemetry rows
python -m solver.generator.export_telemetry --out data/telemetry_all.csv
```

### 4) Run built-in calibration summary on a batch

```bash
cd backend
python -m solver.generator.calibrate --batch phase6_v1
```

This prints per-tier aggregate metrics (score/minutes/undos/rating) and mismatch heuristics to help spot under- or over-classified puzzles.

### 5) Use fixed-seed calibration batches through the API

For development/testing, fixed seed manifests live under:

`backend/solver/generator/calibration_batches/*.json`

You can fetch a batch manifest from:

```bash
curl http://localhost:8000/api/calibration-batch/phase6_v1
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

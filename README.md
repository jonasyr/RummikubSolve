# RummikubSolve

An optimal Rummikub move solver — tells you exactly which tiles to play and how to rearrange the board to maximize tiles placed from your rack.

## Architecture

| Layer    | Technology                                  |
|----------|---------------------------------------------|
| Frontend | Next.js 15, React 19, Tailwind CSS, Zustand |
| Backend  | FastAPI, Python 3.12+, Pydantic v2          |
| Solver   | HiGHS ILP (`highspy`), Python formulation   |
| CI/CD    | GitHub Actions                              |
| Deploy   | Vercel (frontend) + Docker / Fly.io (backend)|

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
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API base URL baked into the frontend bundle |

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
# Frontend → http://localhost:3000
# Backend  → http://localhost:8000
```

### Override env vars

```bash
SENTRY_DSN=https://... ENVIRONMENT=production docker compose up
```

## Development Status

See [CHANGELOG.md](./CHANGELOG.md) for full version history.
See [Blueprint.md](./Blueprint.md) for the design document.

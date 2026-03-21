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

### Docker (full stack)

```bash
docker compose up
```

## Development Status

See [Blueprint.md](./Blueprint.md) for the full design document.

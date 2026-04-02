# Repository Guidelines

## Project Structure & Module Organization
`backend/` contains the FastAPI API and solver. Core logic lives under `backend/solver/` with `engine/`, `generator/`, `models/`, and `validator/`; API entry points are in `backend/api/`; tests live in `backend/tests/`. `frontend/` contains the Next.js app: routes in `frontend/src/app/`, reusable UI in `frontend/src/components/`, client state in `frontend/src/store/`, translations in `frontend/src/i18n/`, unit tests in `frontend/src/__tests__/`, and end-to-end tests in `frontend/e2e/`. Deployment files live in `docker-compose.yml` and `nginx/`.

## Build, Test, and Development Commands
Backend:
- `cd backend && pip install -e ".[dev]"` installs runtime and dev dependencies.
- `cd backend && uvicorn api.main:app --reload --port 8000` runs the API locally.
- `cd backend && pytest -v` runs backend tests.
- `cd backend && pytest -m "not slow"` skips expensive generator and uniqueness tests.

Frontend:
- `cd frontend && npm install` installs dependencies.
- `cd frontend && npm run dev` starts the app on `:3000`.
- `cd frontend && npm run build` builds production assets.
- `cd frontend && npm run test` runs Vitest.
- `cd frontend && npm run e2e` runs Playwright tests against a running backend.

Full stack:
- `docker compose up --build` starts nginx, frontend, and backend together.

## Coding Style & Naming Conventions
Python targets 3.12 with 4-space indentation, `mypy --strict`, and Ruff (`line-length = 100`). Keep module names `snake_case`; prefer explicit types for public solver and API functions. TypeScript/React uses 2-space indentation, PascalCase for components (`RackSection.tsx`), camelCase for hooks/store actions, and colocated tests near feature areas. Keep comments sparse and only where solver logic is non-obvious.

## Testing Guidelines
Backend tests use `pytest`; frontend unit tests use `Vitest` with Testing Library; browser flows use Playwright. Name Python tests `test_*.py`, React tests `*.test.ts(x)`, and e2e specs `*.spec.ts`. Add or update tests for solver rules, API contracts, and user-visible UI behavior whenever code changes those areas.

## Commit & Pull Request Guidelines
Recent history follows Conventional Commits such as `fix(backend): ...`, `perf(ci): ...`, and `chore: ...`; keep using that format. PRs should include a short problem statement, the chosen approach, test coverage run locally, and screenshots or recordings for UI changes. Link the related issue when one exists.

## Configuration & Generated Files
Use `.env` for local configuration and keep secrets out of commits. Do not commit generated artifacts such as `frontend/playwright-report/` or `frontend/test-results/` unless a task explicitly requires them.

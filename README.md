# Universal Web Data Extractor

Extract titles, headings, links, images, tables, meta tags, Open Graph data, and canonical URLs from any public webpage — with a clean React UI, CSV export, and live filtering.

**Live demo:** https://web-scraper-frontend.netlify.app <!-- update after first deploy -->

---

## Features

- SSRF-safe HTTP fetch with full redirect-chain validation
- robots.txt compliance with fail-open policy
- Partial extraction failure isolation — one broken extractor never kills the whole request
- Per-IP rate limiting + global concurrency cap
- In-memory response caching
- CSV export with formula-injection protection
- Client-side keyword search, type filter, hide-empty, and deduplication

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, FastAPI, BeautifulSoup4, Pandas, httpx |
| Frontend | React 19, Vite, Tailwind CSS |
| Testing | pytest, Vitest, React Testing Library |
| Infra | Docker, GitHub Actions, Render (backend), Netlify (frontend) |

---

## Local development

### Prerequisites

- Python 3.11+
- Node 20+
- Docker (optional)

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp ../.env.example ../.env
uvicorn app.main:app --reload
```

API available at `http://localhost:8000`

### Frontend

```bash
cd frontend
npm install
npm run dev
```

UI available at `http://localhost:5173`

### Docker (both services)

```bash
cp .env.example .env
docker compose up --build
```

---

## Running tests

```bash
# Backend
cd backend && pytest

# Frontend
cd frontend && npm test
```

---

## Deployment

### Backend → Render

1. Push to GitHub
2. Create a new **Web Service** on [render.com](https://render.com), connect your repo
3. Render auto-detects `render.yaml` — no manual config needed
4. In **Environment**, set `ALLOWED_ORIGINS` to your Netlify frontend URL

### Frontend → Netlify

1. Connect your repo on [netlify.com](https://netlify.com)
2. Netlify auto-detects `netlify.toml` — build command and publish dir are pre-configured
3. In **Site settings → Environment variables**, add:
   - `VITE_API_BASE` = `https://<your-render-service>.onrender.com/api/v1`

### Production checklist

- [ ] `ALLOWED_ORIGINS` set to Netlify domain only (no `*`, no `localhost`)
- [ ] `VITE_API_BASE` points at the live Render URL
- [ ] Update the live demo link at the top of this README

---

## Environment variables

See `.env.example` for the full list with descriptions.

# HarvestWise Frontend

Streamlit dashboard for the HarvestWise project.

**The backend must be running.** Every number on every page comes from the
FastAPI service, which serves real trained-model output over real ingested
data. There is no local sample-data mode: the dashboard used to fall back to
`components/mock_data.py` whenever a request failed, which meant a demo given
with the backend down displayed fabricated forecasts, an invented benchmark
leaderboard and made-up harvest records that looked exactly like real ones.
That module has been deleted. When a call fails, the page now says why and
stops.

## Setup

```bash
cd frontend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
```

## Run

```bash
streamlit run app.py
```

Opens at http://localhost:8501

## Connecting to the real backend

By default the app looks for a backend at `http://localhost:8000`. Start it
first (see `backend/README.md`):

```bash
cd backend && uvicorn app.main:app --port 8000
```

The sidebar status indicator reads "Connected to live backend" once it is up.
A page whose endpoint returns 503 shows the reason - typically a missing
checkpoint or an un-ingested field - instead of any content.

To point at a different backend URL:

```bash
set HARVESTWISE_BACKEND_URL=http://your-backend-host:8000
streamlit run app.py
```

## Structure

- `app.py` - entrypoint / overview page
- `pages/` - one file per dashboard page (Streamlit auto-generates the sidebar nav from these)
- `components/` - reusable UI pieces (charts, cards, field selector) and the API client
- `components/api_client.py` - the only path to data; fails loudly, never substitutes

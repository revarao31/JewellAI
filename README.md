# JewellAI — Your Smart Jewellery Assistant

A jewellery-focused AI chatbot: React frontend (no build step needed) + a
Flask backend that talks to Google's Gemini API. The API key lives only on
the server.

## Structure
```
jewellai/
├── backend/
│   ├── app.py            # Flask API (chat, health, rate stubs, calculator)
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    └── index.html         # React (via CDN) chat UI, served by Flask
```

## Run it

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# open .env and paste your real Gemini API key into GEMINI_API_KEY
python app.py
```

Then open **http://localhost:5000** — Flask serves the frontend and the API
from the same origin, so there's nothing else to configure.

Get a Gemini API key at https://aistudio.google.com/apikey (free tier is
fine for testing).

## What's implemented

- `POST /api/chat` — sends the full conversation to Gemini, returns a reply.
  Handles missing key, timeouts, rate limits, and empty responses with
  friendly messages instead of raw errors.
- `GET /api/health` — used by the frontend to show the "AI Online" status.
- `GET /api/gold-rate` / `GET /api/silver-rate` — return `available: false`
  honestly rather than a made-up number. Wire a real metals-price API into
  these two functions when you're ready to go live; the frontend and the
  chatbot's own answers are already written to never invent a price.
- `POST /api/calculate` — a plain arithmetic jewellery price estimator
  (metal value + making charge + GST), clearly labeled as an estimate.

## Notes for extending

- The system instruction that shapes JewellAI's tone and safety rules
  (never invent prices, ask clarifying questions before recommending, etc.)
  lives in `SYSTEM_INSTRUCTION` in `backend/app.py`.
- To add a real gold/silver price feed, fill in `gold_rate()` /
  `silver_rate()` in `app.py` and update the "Quick View" logic on the
  frontend if you want it shown in the header.
- The frontend is one self-contained HTML file using React + Babel from a
  CDN, so there's no npm/build step — good for a quick portfolio deploy.
  If you later want a compiled build (smaller, faster, no Babel-in-browser),
  this same component can be dropped into a Vite/CRA project unchanged.

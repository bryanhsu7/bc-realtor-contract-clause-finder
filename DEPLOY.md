# Deploying to Vercel

This app has two parts: a **React frontend** (Vite) and a **Python FastAPI backend**.  
Vercel hosts the frontend. The backend runs elsewhere (e.g. Render or Railway) and the frontend calls it via `VITE_API_URL`.

---

## Overview

1. **Backend** – Deploy the FastAPI app (with Chroma DB and env vars) on Render, Railway, or similar.
2. **Frontend** – Deploy the `frontend/` app on Vercel and set `VITE_API_URL` to your backend URL.

---

## Step 1: Deploy the backend

The backend needs a long‑running server, a writable filesystem for Chroma, and env vars. Vercel’s serverless model doesn’t fit this well, so host it on a platform that runs a normal web process.

### Option A: Render (recommended, free tier)

1. Push your repo to GitHub (if it isn’t already).
2. Go to [render.com](https://render.com) → **New** → **Web Service**.
3. Connect the repo and create a Web Service with:
   - **Root Directory:** leave empty (repo root).
   - **Runtime:** Python 3.
   - **Build Command:**  
     `pip install -r requirements.txt`
   - **Start Command:**  
     `python -m backend.main`  
     or, if you use Gunicorn:  
     `gunicorn backend.main:app -k uvicorn.workers.UvicornWorker -b 0.0.0.0:$PORT`
   - **Instance type:** Free (or paid if you need more resources).

4. In **Environment** add:
   - `OPENAI_API_KEY` = your OpenAI key.
   - Optionally: `VECTOR_DB_PATH`, `COLLECTION_NAME` (defaults are fine if you ingest on this machine).

5. **Important:** The free tier has an ephemeral filesystem. You must either:
   - Run the scrape + ingest **after** each deploy (e.g. in Build Command or a separate one‑off job), or  
   - Use a persistent disk (Render paid feature) or an external vector DB so data survives restarts.

6. Deploy and copy the service URL, e.g. `https://your-app-name.onrender.com`.

### Option B: Railway

1. Go to [railway.app](https://railway.app) and create a project from your repo.
2. Add a service and set:
   - **Build:** `pip install -r requirements.txt`
   - **Start:** `python -m backend.main` (and set `PORT` in env if required by Railway).
3. Add `OPENAI_API_KEY` (and any other env vars).
4. Ensure the Chroma DB and knowledge base are present at runtime (e.g. commit a pre‑built DB or run scrape/ingest in build or a startup script).
5. Deploy and copy the public URL Railway gives you.

---

## Step 2: Deploy the frontend on Vercel

### 2a. Connect the repo

1. Go to [vercel.com](https://vercel.com) and sign in (e.g. with GitHub).
2. **Add New** → **Project** → import your Git repository.
3. Configure the project:
   - **Root Directory:** `frontend`  
     (so Vercel builds from the `frontend/` folder).
   - **Framework Preset:** Vite (or leave as auto‑detected).
   - **Build Command:** `npm run build` (default for Vite).
   - **Output Directory:** `dist` (Vite default).
   - **Install Command:** `npm install` (default).

### 2b. Environment variables

In the same project, open **Settings → Environment Variables** and add:

| Name                | Value                                       | Notes                                   |
|---------------------|---------------------------------------------|-----------------------------------------|
| `VITE_API_URL`      | `https://your-backend-url.com`              | Backend URL from Step 1 (no trailing `/`) |
| `VITE_FEEDBACK_EMAIL` | (optional) `feedback@yourdomain.com`      | Pre‑fills “To” for the feedback mailto  |

Save. Redeploy so the new variables are used in the build (Vite inlines them at build time).

### 2c. Deploy

- If you didn’t change Root Directory before first deploy: set **Root Directory** to `frontend`, save, then trigger a **Redeploy**.
- Otherwise, push to your main branch or click **Redeploy** in the Vercel dashboard.

Your app will be at `https://your-project.vercel.app` (or your custom domain).

---

## Step 3: CORS on the backend

The frontend origin (e.g. `https://your-project.vercel.app`) must be allowed by the backend. In `backend/main.py` the FastAPI app should allow that origin, for example:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://your-project.vercel.app",  # add your Vercel URL
        "https://*.vercel.app",             # or use a pattern if your host supports it
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

If your backend already has a permissive `allow_origins=["*"]` for development, you can leave it for now, or narrow it to your real frontend URL(s) for production.

---

## Step 4: Quick checklist

- [ ] Backend deployed and returning 200 at e.g. `https://your-backend.onrender.com/docs`
- [ ] `OPENAI_API_KEY` (and any needed secrets) set on the backend.
- [ ] Chroma DB (or equivalent) available to the backend and populated (scrape + ingest).
- [ ] Frontend deployed on Vercel with **Root Directory** = `frontend`.
- [ ] `VITE_API_URL` set in Vercel to the backend URL (no trailing slash).
- [ ] Backend allows the Vercel origin in CORS.
- [ ] Optional: `VITE_FEEDBACK_EMAIL` set in Vercel if you use the feedback mailto.

---

## Deploying from the repo root (optional)

If you want Vercel to use the repo root instead of the `frontend` folder, you can use the included `vercel.json` at the project root. It tells Vercel to install and build inside `frontend/` and to serve `frontend/dist`. In that case you do **not** set Root Directory to `frontend` in the Vercel UI; the repo root is the project root and `vercel.json` defines the build.

---

## Troubleshooting

- **“Failed to fetch” / network errors from the app**  
  - Confirm `VITE_API_URL` in Vercel matches the backend URL and that the backend is up.
  - Check backend CORS allows your Vercel origin.

- **Blank or broken app**  
  - Ensure **Root Directory** is `frontend` (or that `vercel.json` is correctly set for a root deploy).
  - Check the build logs for frontend errors.

- **Backend 404 on `/api/...`**  
  - Your backend must serve routes like `/api/chat/stream` and `/api/feedback`. Check `backend/main.py` and the start command on Render/Railway.

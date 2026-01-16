# Deployment Guide — Gradio Scraper UI

This document explains how to build and deploy the Gradio web UI (one-button "Sync now") to popular hosts: Render, Fly.io, and Railway. The repo includes a Dockerfile that uses the Playwright base image so the Playwright fallback (JS-rendered scraping) works out-of-the-box.

Prerequisites
- A Supabase project and the SERVICE ROLE KEY (set securely as env var)
- Telegram API ID and HASH and a channel username
- Docker (for building locally or deploying to services that use Docker)
- An account on Render, Fly.io or Railway

Environment variables
Set these in your host's environment configuration (do NOT commit them):

- SUPABASE_URL — your Supabase URL (e.g. https://xyz.supabase.co)
- SUPABASE_SERVICE_ROLE_KEY — Supabase service role key (keep secret)
- TG_API_ID — Telegram API ID
- TG_API_HASH — Telegram API hash
- TG_CHANNEL — Telegram channel username (without @)
- THREADS_USERNAME — Threads username (without @) or THREADS_RSS — RSS feed URL
- BASIC_AUTH_USER — optional: username to protect the UI
- BASIC_AUTH_PASS — optional: password to protect the UI

Local Docker build and run

1. Build the image:

```bash
docker build -t social-sync:latest .
```

2. Run the container (pass env vars):

```bash
docker run --rm -it -p 7860:7860 \
  -e SUPABASE_URL="$SUPABASE_URL" \
  -e SUPABASE_SERVICE_ROLE_KEY="$SUPABASE_SERVICE_ROLE_KEY" \
  -e TG_API_ID="$TG_API_ID" \
  -e TG_API_HASH="$TG_API_HASH" \
  -e TG_CHANNEL="$TG_CHANNEL" \
  -e THREADS_USERNAME="$THREADS_USERNAME" \
  -e BASIC_AUTH_USER="$BASIC_AUTH_USER" \
  -e BASIC_AUTH_PASS="$BASIC_AUTH_PASS" \
  social-sync:latest
```

Open http://localhost:7860 in your browser. If BASIC_AUTH_USER/PASS are set, Gradio will ask for credentials.

Render (Docker)

1. Create a new Web Service on Render and choose "Deploy from Dockerfile".
2. Connect your GitHub repo (or push the image to DockerHub and use the image).
3. In Render service settings, set the environment variables listed above.
4. Set the Port to 7860 if Render doesn't auto-detect it.
5. Deploy — Render will build the image, run it, and provide a HTTPS URL.

Fly.io

1. Install flyctl and authenticate.
2. Run `fly launch` from the repo root and follow prompts. Choose a region.
3. Add your environment variables:

```bash
fly secrets set SUPABASE_URL=$SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY=$SUPABASE_SERVICE_ROLE_KEY TG_API_ID=$TG_API_ID TG_API_HASH=$TG_API_HASH TG_CHANNEL=$TG_CHANNEL THREADS_USERNAME=$THREADS_USERNAME BASIC_AUTH_USER=$BASIC_AUTH_USER BASIC_AUTH_PASS=$BASIC_AUTH_PASS
```

4. Deploy with `fly deploy`.

Railway

1. Connect your GitHub repo or Dockerfile to Railway and create a new project.
2. Set environment variables in Railway's dashboard (same list as above).
3. Configure the start command if required: `python server.py` and ensure port 7860 is exposed.

Security and notes
- Protect your Supabase service role key — use secret management offered by your host.
- If you don't want Playwright (heavy), remove Playwright from `requirements.txt` and the Dockerfile base; the app will still use the requests/RSS approach but may not render JS-only content.
- Consider adding HTTPS and additional auth in front of the service (nginx basic auth, cloud provider auth, or Gradio's own auth).

Troubleshooting
- Playwright browser errors: if browsers fail to launch in your chosen environment, prefer the Playwright Docker base image (already used here). For Alpine-based images additional dependencies are required.
- If you get duplicate-key errors when inserting into Supabase, ensure your `posts` table schema matches (unique constraint on (platform, post_url)). The app attempts to handle duplicates gracefully but the DB schema affects behavior.

Questions or next steps
- I can create a GitHub Actions workflow to build and push a Docker image automatically.
- I can produce a smaller Dockerfile without Playwright to reduce image size if you don't need JS-rendered scraping.

*** End of guide ***

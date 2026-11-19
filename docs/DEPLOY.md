# Deploying the hosted demo (judges only)

The organisers allow, and encourage, a **password-protected** web demo for judges (Cloud9 Discord, 2026-11-18). The GRID licence still forbids derived data on an open website, so:

- Every page, API call and map image needs the password (`api/auth.py`). Only `/health` is open, and it returns no data.
- The deployed image **refuses to start without a password** (`SCOPEWATCH_REQUIRE_AUTH=1`).
- Pages send `X-Robots-Tag: noindex`, `robots.txt` disallows everything, and the API docs page is off.
- The data bundle lives in git-ignored `cache/demo/`. It goes only into the host's **private** image registry, never to GitHub or a public registry.

The app runs as one container: the FastAPI server also serves the built React app. It needs about 600 MB of disk and 1 GB of memory.

## Steps (Fly.io)

Fly builds the image on its own servers from your local folder, so you don't need Docker.

1. **Install `flyctl`** from fly.io's official instructions, then sign in with `fly auth login`. Creating the account is yours to do; Fly may ask for a card even on its small plans.
2. **Build the web app and the data bundle** from the repo root:
   ```bash
   cd web && npm run build && cd ..
   python -m scripts.bundle_demo            # add --with-vod to include your saved VOD links
   ```
3. **Create the app without deploying.** Fly app names are global, so pick a unique one:
   ```bash
   fly launch --no-deploy --copy-config --name <your-unique-name>
   ```
4. **Set the password as a secret.** Choose a strong one, and never put it in a file or commit:
   ```bash
   fly secrets set SCOPEWATCH_PASSWORD=<strong-password> SCOPEWATCH_USER=judge
   ```
5. **Deploy.** This uploads about 600 MB, so the first deploy takes a while:
   ```bash
   fly deploy
   ```
6. **Check it:**
   - `https://<your-unique-name>.fly.dev/health` returns `{"ok": true}`.
   - The site asks for a username and password; the app loads after you log in.
   - `curl -s -o /dev/null -w "%{http_code}" https://<your-unique-name>.fly.dev/api/catalog` returns `401`.
7. **During judging (Jan 27 – Feb 3)**, keep one machine running so judges never wait for a cold start: set `min_machines_running = 1` in `fly.toml` and run `fly deploy` again. Set it back to 0 afterwards.

Give the judges the URL, username and password only where judges see them (a judges-only field of the Devpost submission). Never put them in the README or the public description.

## Updating

After rebuilding the store, the maps or the WPA scores, rerun step 2, then `fly deploy`. Reports are cached in memory per filter, and a restart (which every deploy does) clears the cache.

## Running the same thing locally

```bash
SCOPEWATCH_CACHE=$PWD/cache/demo SCOPEWATCH_REQUIRE_AUTH=1 SCOPEWATCH_PASSWORD=<pw> uvicorn api.server:app --port 8090
```
Then open http://localhost:8090 and log in as `judge`.

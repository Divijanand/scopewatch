# Deploying the hosted demo

**Live:** https://scopewatch-c9.fly.dev (Fly.io app `scopewatch-c9`, one shared-cpu-1x machine with 1 GB in `sjc`), deployed 2026-11-19. **Open, no login, since 2026-11-21** (D-022).

**How it's open now:** on 2026-11-21 the organisers confirmed that apps may serve statistics and per-event data derived from the GRID files for the hackathon. We unset the `SCOPEWATCH_PASSWORD` and `SCOPEWATCH_USER` secrets and set the secret `SCOPEWATCH_REQUIRE_AUTH=0`, which overrides the image's `=1`. The image itself wasn't rebuilt. `robots.txt` still disallows all crawling. Without the password the noindex header and the hidden API docs page no longer apply; both are tied to auth in the current image. Checked live on 2026-11-21: the page, `/api/catalog` and `/health` return 200 with no login.

To put the password back: `fly secrets set SCOPEWATCH_PASSWORD='<strong-password>' SCOPEWATCH_USER=judge -a scopewatch-c9` (and unset `SCOPEWATCH_REQUIRE_AUTH`, so the image's refuse-to-start check applies again).

The rest of this page describes the original password-protected setup (2026-11-18 to 2026-11-21). Then, the organisers allowed and encouraged a **password-protected** web demo for judges, and we read the licence as forbidding derived data on an open website, so:

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
3. **Create the app without deploying.** Fly app names are global, and the name in `fly.toml` must match:
   ```bash
   fly apps create scopewatch-c9 --org personal
   ```
4. **Set the password as a secret.** Choose a strong one, and never put it in a file, a commit or a chat:
   ```bash
   fly secrets set --stage SCOPEWATCH_PASSWORD='<strong-password>' SCOPEWATCH_USER=judge -a scopewatch-c9
   ```
   `fly secrets list -a scopewatch-c9` should then show both names as `Staged`. To change the password later, run the same command without `--stage`; Fly restarts the machine with the new value, without re-uploading.
5. **Deploy.** This uploads about 575 MB, so the first deploy takes a while:
   ```bash
   fly deploy --remote-only -a scopewatch-c9
   fly scale count 1 --yes -a scopewatch-c9
   ```
   Fly creates a second machine for redundancy on the first deploy. Scale back to one: that halves the cost, and VOD links saved by judges stay on one machine.
6. **Check it:**
   - `https://scopewatch-c9.fly.dev/health` returns 200, with only the dataset and parser versions.
   - The site asks for a username and password; the app loads after you log in.
   - `curl -s -o /dev/null -w "%{http_code}" https://scopewatch-c9.fly.dev/api/catalog` returns `401`.

   Checked on the live site on 2026-11-19: the page, API calls, map images, reports, the docs page and robots.txt all return 401 without the password or with a wrong one; `http://` redirects to `https://`; responses carry `X-Robots-Tag: noindex`. The owner logged in and confirmed the app and data load.
7. **During judging (Jan 27 – Feb 3)**, keep one machine running so judges never wait for a cold start: set `min_machines_running = 1` in `fly.toml` and run `fly deploy` again. Set it back to 0 afterwards.

Give the judges the URL, username and password only where judges see them (a judges-only field of the Devpost submission). Never put them in the README or the public description.

## Updating

After rebuilding the store, the maps or the WPA scores, rerun step 2, then `fly deploy`. Reports are cached in memory per filter, and a restart (which every deploy does) clears the cache.

## Running the same thing locally

```bash
SCOPEWATCH_CACHE=$PWD/cache/demo SCOPEWATCH_REQUIRE_AUTH=1 SCOPEWATCH_PASSWORD=<pw> uvicorn api.server:app --port 8090
```
Then open http://localhost:8090 and log in as `judge`.

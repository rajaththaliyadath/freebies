# Freebies Agent

Modular Python agent that scrapes OzBargain freebies, filters with an LLM layer, deduplicates with SQLite, and sends alerts to Telegram/Discord.

## Local Run

1. Create `.env` with at least:
   - `TELEGRAM_BOT_TOKEN=...`
   - `TELEGRAM_CHAT_ID=...`
2. Install dependencies:
   - `pip install -r requirements.txt`
   - `python -m playwright install chromium`
3. Run:
   - `python main.py`

## Docker Run

```bash
docker compose up -d --build
```

After startup:
- Scraper runs in `freebies-agent`
- Homepage dashboard runs on `http://YOUR_DROPLET_IP:3000`

## Production Architecture

This project is designed for a simple cloud deployment on a DigitalOcean Basic Droplet:

- **Compute:** 1x DigitalOcean Basic Droplet (`$6/mo`, size `s-1vcpu-1gb`)
- **Container runtime:** Docker Engine + Docker Compose plugin
- **App runtime:** Python agent inside a Playwright-ready image (`mcr.microsoft.com/playwright:v1.40.0-jammy`)
- **Persistence:** SQLite database mounted to host volume (`./data/deals.db`) so restarts do not lose seen-deal state
- **Secrets/config:** `.env` mounted read-only into the container and also loaded via Compose `env_file`
- **Resilience:** `restart: always` in `docker-compose.yml` to auto-restart after crashes or host reboot

### Deployment flow

`deploy.sh` automates:

1. SSH into droplet
2. Install Docker if missing
3. Clone/pull latest GitHub code
4. Build and run container with:
   - `docker compose up -d --build`

## Dashboard (Homepage)

This repo includes a Homepage dashboard (`gethomepage/homepage`) as a central command center.

- **Dashboard service:** `homepage` container
- **URL:** `http://YOUR_DROPLET_IP:3000`
- **Config path:** `config/`
  - `config/services.yaml` - app cards (Portfolio, OzBargain Bot, Freebies Tracker)
  - `config/widgets.yaml` - server CPU, RAM, and disk usage widget
  - `config/settings.yaml` - dark-mode styling and Docker provider setup

Homepage can inspect Docker container health/status via:
- shared Docker socket mount (`/var/run/docker.sock`)
- shared Compose network (`command-center`)

### Deploy command

```bash
chmod +x deploy.sh
DROPLET_IP=YOUR_DROPLET_IP ./deploy.sh
```

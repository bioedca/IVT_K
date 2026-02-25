# IVT Kinetics Analyzer — Deployment Guide

## Overview

Single-tenant scientific web application for analyzing in-vitro transcription
kinetics. Designed to run on a personal Linux server or WSL2 instance, accessed
exclusively through a Tailscale mesh VPN.

**Stack**: Flask + Dash · SQLite (WAL mode) · Huey task queue · PyMC (Bayesian MCMC)

## Prerequisites

- Ubuntu 20.04+ (or WSL2 with systemd enabled)
- Python 3.11+
- Miniconda (recommended) with `IVT_K` environment
- Tailscale account (free tier is sufficient)
- ~4 GB RAM minimum (8 GB recommended for MCMC analysis)

## Tailscale Network Setup

The application relies on Tailscale for all network access. Tailscale creates a
zero-trust mesh VPN using WireGuard encryption, meaning every connection between
your devices is end-to-end encrypted. No port forwarding, no dynamic DNS, and no
exposure to the public internet.

### Why Tailscale

- **Zero-trust networking**: every device authenticates individually; there is
  no trusted LAN.
- **WireGuard-based encryption**: all traffic is encrypted in transit with
  modern, audited cryptography.
- **No port forwarding**: the server does not need any ports open to the
  internet. Your router firewall stays closed.
- **Network-level access control**: only devices authenticated to your
  tailnet can connect. The app reads a trust-based `X-Username` header
  for audit logging (set by the client, defaults to `anonymous`).

### Installation

```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Authenticate (opens a browser window for login)
sudo tailscale up

# Verify your Tailscale IP
tailscale ip -4
```

### MagicDNS

Once Tailscale is running, you can access the app using a human-readable
hostname instead of memorizing IP addresses:

```
http://<hostname>.<tailnet-name>.ts.net:8050
```

MagicDNS is enabled by default on most Tailscale accounts. Check your admin
console at https://login.tailscale.com if DNS resolution is not working.

### Firewall Lockdown

Even though the app binds to `0.0.0.0` in production (so it listens on all
interfaces), UFW ensures that only traffic arriving over the Tailscale interface
can reach it:

```bash
# Reset firewall to deny all incoming by default
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow all traffic on the Tailscale interface only
sudo ufw allow in on tailscale0

# Enable the firewall
sudo ufw enable

# Verify rules
sudo ufw status verbose
```

With these rules in place, port 8050 is unreachable from the local network or
the internet. Only devices authenticated to your Tailscale tailnet can connect.

### Sharing Access with Collaborators

To give a collaborator access to the application:

1. **Invite them to your Tailscale tailnet** via the admin console at
   https://login.tailscale.com → Users → Invite.
2. They install Tailscale on their device and authenticate.
3. Once connected, they can access the app at the same MagicDNS URL.
4. They set their username via the `X-Username` header (trust-based;
   defaults to `anonymous` if not provided). This value appears in audit logs.

No firewall changes, VPN credentials, or port forwarding needed — Tailscale
handles all of it.

### Tailscale ACLs (Optional)

For fine-grained control, Tailscale ACLs can restrict which devices or users
can reach port 8050:

```json
{
  "acls": [
    {
      "action": "accept",
      "src": ["group:lab-members"],
      "dst": ["ivt-server:8050"]
    }
  ]
}
```

Edit ACLs at https://login.tailscale.com → Access Controls. This is optional —
by default, all devices on your tailnet can reach each other.

### How User Identity Works

1. A user connects to the app through Tailscale (only authenticated tailnet
   members can reach the server).
2. The app reads the `X-Username` header from each request for audit logging.
3. This header is **trust-based**: the client sets it, and the app records the
   value. Tailscale provides network-level authentication (ensuring only
   authorized devices connect), but does not automatically inject identity
   headers.
4. No passwords or sessions are needed — access control comes from the network
   layer.

## Development Mode

For local development, no Tailscale or `.env` file is needed:

```bash
# Terminal 1: Start the web application (hot reload enabled)
python run.py
# Runs at http://127.0.0.1:8050 with debug=true

# Terminal 2: Start the Huey background worker (required for MCMC tasks)
python scripts/run_huey_worker.py
```

In development mode a default `SECRET_KEY` is used automatically. Do not deploy
with the default key — production requires an explicit key in `.env`.

### Development vs Production at a Glance

| Aspect | Development | Production |
|--------|------------|------------|
| Command | `python run.py` | `python run.py --production --host 0.0.0.0` |
| Debug / hot reload | Yes | No |
| SECRET_KEY | Auto-generated dev key | Required in `.env` |
| IVT_SIGNING_KEY | Not needed | Required in `.env` |
| Network access | localhost only (127.0.0.1:8050) | Tailscale VPN (0.0.0.0 + UFW firewall) |
| Background worker | Manual: `python scripts/run_huey_worker.py` | systemd: `ivt-worker.service` |
| Database backups | Manual | Automatic daily via `ivt-backup.timer` |
| Logging | Console, DEBUG level | JSON to `logs/`, INFO level |
| Process management | Ctrl+C to stop | systemd auto-restart on crash |
| PIN access gate | Optional | Recommended (`IVT_ACCESS_PIN` in `.env`) |

## Production Deployment

### 1. Environment Setup

```bash
# Create and configure .env from the provided template
cp .env.example .env

# Edit .env and set at minimum:
#   FLASK_ENV=production
#   SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
#   IVT_SIGNING_KEY=<generate the same way>
#   Optional: IVT_ACCESS_PIN=<your-pin>
```

The `EnvironmentFile` directive in `ivt-app.service` loads these variables at
service start. The leading `-` means the service will not fail if the file is
missing (but production should always have one).

### 2. Initialize Database

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate IVT_K
python scripts/init_db.py
```

This runs any pending Alembic migrations. If the database does not exist yet, it
falls back to `db.create_all()` and stamps the Alembic head.

### 3. Install systemd Services

```bash
# Copy all service and timer files
sudo cp deploy/ivt-app.service /etc/systemd/system/
sudo cp deploy/ivt-worker.service /etc/systemd/system/
sudo cp deploy/ivt-backup.service /etc/systemd/system/
sudo cp deploy/ivt-backup.timer /etc/systemd/system/
sudo cp deploy/ivt-inactivity-check.service /etc/systemd/system/
sudo cp deploy/ivt-inactivity-check.timer /etc/systemd/system/

# Reload systemd to pick up new files
sudo systemctl daemon-reload

# Enable services to start on boot
sudo systemctl enable ivt-app
sudo systemctl enable ivt-worker
sudo systemctl enable ivt-backup.timer
sudo systemctl enable ivt-inactivity-check.timer

# Start everything
sudo systemctl start ivt-app
sudo systemctl start ivt-worker
sudo systemctl start ivt-backup.timer
sudo systemctl start ivt-inactivity-check.timer
```

### 4. Verify

```bash
# Check that the app and worker are running
systemctl status ivt-app ivt-worker

# Confirm the timers are scheduled
systemctl list-timers | grep ivt

# Hit the health endpoint
curl -s http://localhost:8050/health
```

## Service Architecture

```
  Long-running services
  ─────────────────────
  ivt-app.service              Web application (Flask + Dash, port 8050)
         ▲
         │  Requires ivt-app
  ivt-worker.service           Huey background worker (MCMC, exports)

  Timer-triggered oneshots
  ────────────────────────
  ivt-backup.timer  ──────►  ivt-backup.service
    (daily, midnight)            Runs: python scripts/backup.py --cleanup

  ivt-inactivity-check.timer ──►  ivt-inactivity-check.service
    (weekly, Sunday 6 AM)            Runs: python scripts/check_inactive_projects.py --warn
```

- **ivt-app** and **ivt-worker** are long-running (`Type=simple`). systemd
  restarts them automatically if they crash (`Restart=always`).
- **ivt-backup** and **ivt-inactivity-check** are oneshot services triggered by
  their respective timers. They run once and exit.
- The worker depends on the app (`Requires=ivt-app.service`), so starting the
  worker will also start the app if it is not already running.

## Database Management

All migration commands use the project-local Alembic config:

```bash
# Apply all pending migrations
alembic -c alembic/alembic.ini upgrade head

# Roll back one migration
alembic -c alembic/alembic.ini downgrade -1

# Show current migration version
alembic -c alembic/alembic.ini current

# Show full migration history
alembic -c alembic/alembic.ini history
```

### init_db.py Options

```bash
# Standard init: run migrations, fallback to db.create_all() if needed
python scripts/init_db.py

# Reset: wipe the database and recreate from scratch
python scripts/init_db.py --reset

# Nuke: complete reset — deletes DB, uploads, traces, checkpoints, and logs
# (prompts for confirmation)
python scripts/init_db.py --nuke
```

### Migration Notes

- Always back up the database before running migrations.
- SQLite does not support `ALTER COLUMN`. Review autogenerated migrations and
  remove any `op.alter_column()` calls — use batch operations instead.
- Test migrations against a copy of the production database before applying.

### Migration History

The database schema has evolved through 9 Alembic migrations:

| # | Migration | Description |
|---|-----------|-------------|
| 1 | `22ec2d6034b4` | Initial schema — all core tables |
| 2 | `b4f2a8c91d03` | Add indexes on frequently queried FK columns |
| 3 | `a3b7c9e2f401` | Add access_logs table |
| 4 | `d9354085474a` | Add model_residuals column to analysis_versions |
| 5 | `8ff2e5422fc8` | Add protocol history fields to reaction_setups |
| 6 | `81915dfa5605` | Add ligand_condition to WellAssignment, Well, FoldChange, HierarchicalResult |
| 7 | `09354998e331` | Add plasmid_size_bp to constructs (nM-based DNA targeting) |
| 8 | `b078f506e286` | Merge migration heads |
| 9 | `add_exclude_from_fc` | Add exclude_from_fc column to wells (R² quality filter) ¹ |

¹ Migration 9 uses a human-readable slug as its revision ID (via `revision_id` override)
rather than the standard 12-character hex hash used by migrations 1–8. This is intentional
for readability in `alembic history` output.

Running `python scripts/init_db.py` applies all pending migrations automatically.
For a fresh install, it falls back to `db.create_all()` and stamps the Alembic
head so future migrations work correctly.

## Backup & Recovery

### Automated Daily Backups

The `ivt-backup.timer` triggers a backup every day at midnight. Old backups are
pruned automatically (30-day retention by default).

### Manual Backup

```bash
# Create a backup and clean up old ones
python scripts/backup.py --cleanup

# Or trigger via systemd
sudo systemctl start ivt-backup.service
```

### Restore from Backup

```bash
# List available backups
python scripts/backup.py --list

# Restore a specific backup
python scripts/backup.py --restore backup_2026-01-15_00-00-00.tar.gz
```

### What Is Included

Backups capture the database, project data, and configuration. They are stored
as timestamped `.tar.gz` archives in the `backups/` directory with accompanying
metadata JSON files.

## Monitoring & Logs

### journalctl (systemd logs)

```bash
# Follow app logs in real time
sudo journalctl -u ivt-app -f

# Follow worker logs
sudo journalctl -u ivt-worker -f

# Last 50 lines of backup output
sudo journalctl -u ivt-backup -n 50

# Inactivity check results
sudo journalctl -u ivt-inactivity-check -n 50
```

### JSON Application Logs

The app and worker also write structured JSON logs to disk:

```bash
# Application log
tail -f logs/app.jsonl | python -m json.tool

# Worker log
tail -f logs/worker.jsonl | python -m json.tool
```

### Health Endpoints

- `GET /health` — basic health check (returns 200 if the app is running)
- `GET /api/status` — detailed status including database connectivity and
  worker state

### Resource Limits

Resource limits are defined in the service files to prevent runaway processes:

- **ivt-app.service**: `MemoryMax=4G`, `CPUQuota=200%`
- **ivt-worker.service**: `MemoryMax=8G`, `CPUQuota=400%`

## Troubleshooting

### Service Won't Start

```bash
# Check the last 50 log lines for the failing service
sudo journalctl -u ivt-app -n 50

# Verify the conda environment has all dependencies
conda activate IVT_K && python -c "import dash; import pymc; print('OK')"

# Check file permissions on the working directory
ls -la /home/bioedca/IVT_KINETICS_ANALYZER/

# Ensure .env exists and has a valid SECRET_KEY for production
cat /home/bioedca/IVT_KINETICS_ANALYZER/.env
```

### Database Locked

If you see "database is locked" errors, the WAL file may need checkpointing:

```bash
# Stop both services
sudo systemctl stop ivt-app ivt-worker

# Force a WAL checkpoint
sqlite3 ivt_kinetics.db "PRAGMA wal_checkpoint(TRUNCATE);"

# Restart services
sudo systemctl start ivt-app ivt-worker
```

### Worker Out of Memory

If MCMC analysis causes the worker to be OOM-killed:

1. Edit the service file: `sudo systemctl edit ivt-worker`
2. Add an override increasing `MemoryMax` (e.g., `MemoryMax=12G`)
3. Reload and restart: `sudo systemctl daemon-reload && sudo systemctl restart ivt-worker`

### Migration Failures

```bash
# Always backup first
python scripts/backup.py

# Check which migration is currently applied
alembic -c alembic/alembic.ini current

# Examine the failing migration file in alembic/versions/
# Remember: SQLite does not support ALTER COLUMN — remove those calls
```

### Stale PID / Port Already in Use

```bash
# Check what is using port 8050
lsof -i :8050

# Kill the stale process if needed
kill <PID>

# Then restart the service
sudo systemctl start ivt-app
```

## Security Notes

- **Network isolation**: the app is only accessible via Tailscale. UFW blocks
  all traffic that does not arrive over the `tailscale0` interface.
- **User identity**: access control is handled at the network layer (only
  Tailscale-authenticated devices can connect). The app reads a trust-based
  `X-Username` header for audit logging. No passwords are stored or managed
  by the app.
- **Optional PIN gate**: set `IVT_ACCESS_PIN` in `.env` for an additional
  access control layer on top of Tailscale.
- **CSRF protection**: Flask-WTF protects all Flask routes. Dash internal
  callback routes are exempt (they use their own request validation).
- **Rate limiting**: 100 requests/min for reads, 30/min for writes, 5/min for
  analysis endpoints.
- **Service hardening**: all systemd services run with `NoNewPrivileges=true`,
  `ProtectSystem=strict`, `ProtectHome=read-only`, and `PrivateTmp=true`.
  Write access is limited to the application directory via `ReadWritePaths`.

## Daily Report & Export

The application generates PDF daily reports via WeasyPrint with:

- **Aggregated fold change tables** grouped by construct x comparison type x ligand condition
- **Fitted curve plots** via Plotly Kaleido (static image export using headless Chrome)
- **Plate layout heatmaps** with construct color coding
- **QC summary** with flagged wells and exclusion counts

Reports can be filtered to specific plates and exported from the Publication
Export page (`/export`).

### Publication Packages

Reproducibility packages include:

- Raw data files (CSV)
- MCMC traces (NetCDF)
- Fitted parameters with confidence intervals
- Validation certificates signed with `IVT_SIGNING_KEY`
- Methods text auto-generated from analysis parameters

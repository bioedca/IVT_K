# IVT Kinetics Analyzer

A scientific web application for analyzing in-vitro transcription (IVT) kinetics of riboswitch constructs using fluorogenic aptamer reporters. The application guides researchers from experimental design through data collection to final parameter estimation with dual statistical methods (Bayesian MCMC and Frequentist).

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Features

### Experimental Design & Planning
- **Smart Planner**: AI-powered experiment suggestions based on current data and precision targets
- **Power Analysis**: Pre-experiment, mid-experiment, and post-hoc statistical power calculations
- **Reaction Calculator**: Master mix and dilution series calculations with protocol generation
- **Plate Layout Editor**: Visual layout design with pattern fill, checkerboard support for 384-well plates
- **nM-Based DNA Targeting**: Automatic molar concentration calculations from plasmid size for precise template dosing
- **Digestion Calculator**: Standalone restriction enzyme digestion calculator for linearizing plasmid DNA (NEB workflow)

### Data Management

- **BioTek File Import**: Parse raw plate reader data with automatic temperature drift detection
- **Construct Registry**: Organize constructs by T-box family with wild-type and control tracking
- **Plate Templates**: Reusable layout templates instantiated per plate
- **Project Archival**: Compress and archive inactive projects with on-demand restore
- **Repair Wizard**: Fix data parsing issues with a guided step-by-step wizard
- **Warning Suppression**: Suppress QC warnings (incomplete plate, temperature deviation, low replicate count, etc.) with mandatory justification for audit trail

### Analysis Pipeline
- **Curve Fitting**: Automatic fitting of multiple kinetic models to all wells
- **Dual Statistical Methods**: Both Bayesian (PyMC/MCMC) and Frequentist analysis run automatically
- **Hierarchical Modeling**: Multivariate models with correlated random effects across parameters
- **Fold Change Estimation**: Within-family and cross-family comparisons with variance inflation tracking
- **Quality Control**: Automatic flagging of outliers, CV thresholds, background stability index
- **Negative Control Dashboard**: Background estimation, signal-to-noise ratio, background stability index, LOD/LOQ calculations
- **Ligand Condition Pipeline**: End-to-end +Lig/-Lig experimental design, plate assignment, and within-condition vs ligand-effect comparisons
- **Per-Family Hierarchical Models**: Independent Bayesian and Frequentist models per construct family with family-specific variance components
- **Construct Scoring Reform**: Probability-based experiment prioritization with P(meaningful effect) from Bayesian posteriors

### Visualization & Export
- **Interactive Plots**: Curve browser, forest plots, violin plots, Q-Q plots, plate heatmaps
- **Comparison Sets**: Build custom well comparison sets with side-by-side visualization
- **Publication Packages**: Reproducibility packages with raw data, traces, and validation certificates
- **Cross-Project Comparison**: Compare constructs across multiple projects (read-only)
- **Methods Text Generation**: Auto-generated methods section for publications with user editing and diff tracking
- **Precision Dashboard**: Track confidence interval width targets across constructs
- **Workflow Stepper**: Guided multi-step workflow with automatic step unlocking
- **Access Log Viewer**: Browse PIN gate access attempts and user sessions (`/admin/access-log`)

### Infrastructure

- **Background Tasks**: Long-running MCMC analysis via Huey task queue with checkpointing
- **Audit Logging**: Full audit trail with user attribution via Tailscale identity
- **REST API**: Complete API with OpenAPI 3.0 documentation (Swagger UI at `/api/docs`)
- **Plugin System**: Extensible kinetic model architecture
- **Conflict Detection**: Last-write-wins resolution with concurrent edit warnings
- **Scientific Editorial Theme**: Custom design theme with Instrument Serif, Source Sans 3, and JetBrains Mono fonts; dark mode support via Mantine
- **Contextual Help**: JSON-driven help panels, tooltips, and glossary integrated throughout the UI

---

## Requirements

- Python 3.11+
- Miniconda (recommended) or virtualenv
- ~4 GB RAM minimum (8 GB recommended for MCMC analysis)
- Modern browser (Chrome 90+, Firefox 88+, Safari 14+, Edge 90+)
- Desktop only (minimum viewport: 1024×768; mobile devices are not supported)
- Tailscale account for production deployment (free tier is sufficient)

---

## Quick Start

### Development Mode

No Tailscale, no `.env` file, no configuration required. The application runs on localhost with hot reload enabled, using an auto-generated development key.

```bash
# Terminal 1: Start the web application (hot reload enabled)
python run.py
# Runs at http://127.0.0.1:8050 with debug=true

# Terminal 2: Start the Huey background worker (required for MCMC tasks)
python scripts/run_huey_worker.py
```

Open http://127.0.0.1:8050 in your browser. Both terminals must remain open during development. Stop either process with `Ctrl+C`.

### Production Mode

Production deployment requires a `.env` file with a `SECRET_KEY`, Tailscale for network access, and systemd for process management. See the [Deployment](#deployment) section for the full setup guide.

```bash
# Quick start (if .env and Tailscale are already configured)
python run.py --production --host 0.0.0.0
```

Access the application at `http://<hostname>.<tailnet-name>.ts.net:8050` from any device on your Tailscale network.

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/bioedcam/IVT_Kinetics_Analyzer.git
cd IVT_Kinetics_Analyzer
```

### 2. Create Conda Environment

```bash
# Create environment with all production dependencies
conda env create -f environment.yml
conda activate IVT_K

# For development (adds pytest, ruff, mypy, etc.)
pip install -r requirements-dev.txt
```

### 3. Alternative: pip Installation

If you prefer pip over conda:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For development
```

Note: Scientific dependencies (NumPy, SciPy, PyMC) may require additional system libraries when installed via pip. The conda path handles these automatically. See `scripts/setup_environment.sh` for system dependency installation.

### 4. Initialize Database

```bash
python scripts/init_db.py
```

This script performs the following steps:

1. Checks whether the SQLite database file exists.
2. If a database exists, runs all pending Alembic migrations (`alembic upgrade head`).
3. If no database exists, falls back to `db.create_all()` to build the schema from ORM models, then stamps the Alembic head so future migrations start from the correct point.
4. Enables WAL (Write-Ahead Logging) mode for concurrent reads.

The Alembic configuration file lives at `alembic/alembic.ini`. All Alembic commands must reference it explicitly:

```bash
alembic -c alembic/alembic.ini upgrade head
```

See the [Database](#database) section for migration details.

### 5. (Optional) Seed Sample Data

```bash
# Seed a minimal dataset for development
python scripts/seed_data.py

# Seed a full dataset with more constructs and sessions
python scripts/seed_data.py --full

# Clean existing data before seeding (prompts for confirmation)
python scripts/seed_data.py --clean --full -v
```

---

## Configuration

Configuration is managed through `app/config.py` with environment-specific classes:

### Environment Variables

| Environment Variable | Description | Default |
|---------------------|-------------|---------|
| `FLASK_ENV` | Environment mode (`development`, `production`, `testing`) | `development` |
| `SECRET_KEY` | Session security key (required in production) | dev key |
| `IVT_SIGNING_KEY` | HMAC key for publication certificate signatures (required in production) | dev key |
| `LOG_LEVEL` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` |
| `DEBUG` | Enable debug mode and hot reload | `true` in dev |
| `HOST` (or `IVT_HOST`) | Server host | `127.0.0.1` |
| `PORT` (or `IVT_PORT`) | Server port | `8050` |
| `IVT_ACCESS_PIN` | PIN required to access the app (disabled when unset) | *(none)* |

### Key Configuration Parameters

```python
# Analysis defaults
DEFAULT_MODEL = "plateau"          # Default kinetic model
MCMC_DEFAULT_SAMPLES = 2000        # MCMC samples per chain
MCMC_DEFAULT_CHAINS = 4            # Number of MCMC chains
MCMC_DEFAULT_TUNE = 1000           # MCMC tuning samples

# File limits
MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50 MB max upload
ALLOWED_EXTENSIONS = {".txt", ".csv", ".tsv", ".xlsx", ".xls"}

# Request timeouts
REQUEST_TIMEOUT_DEFAULT = 30       # 30s for standard requests
REQUEST_TIMEOUT_ANALYSIS = 300     # 5 min for MCMC/analysis
REQUEST_TIMEOUT_EXPORT = 120       # 2 min for export operations
```

### PIN Access Gate

Tailscale ensures only authenticated devices on your tailnet can reach the
server, but anyone on that tailnet can access the app. The PIN gate adds an
application-level barrier so that only people who know the PIN can actually
use the UI — useful when your tailnet includes collaborators, family members,
or shared devices that should not have unrestricted access.

When the `IVT_ACCESS_PIN` environment variable is set, every request (except
`/auth/*` and `/api/health/*`) requires a valid session cookie obtained by
entering the correct PIN.

```bash
# Enable the PIN gate (use a strong PIN, 6+ digits recommended)
export IVT_ACCESS_PIN="<your-pin-here>"
python run.py
```

For persistent deployment, add it to your `.env` file:

```bash
# In .env
IVT_ACCESS_PIN=<your-pin-here>
```

Once enabled, users see a self-contained HTML login page. After entering the
correct PIN the session is stored in a cookie and persists until logout or
session expiry. All PIN attempts — successful and failed — are rate-limited
(5/min) and logged to the Access Log (`/admin/access-log`) with IP address
and timestamp.

To disable the gate, remove or comment out the variable:

```bash
unset IVT_ACCESS_PIN  # or remove from .env
```

---

## Deployment

### Development vs Production

| Aspect | Development | Production |
|--------|------------|------------|
| Entry point | `python run.py` | `python run.py --production --host 0.0.0.0` |
| Debug mode | Enabled (hot reload) | Disabled |
| SECRET_KEY | Auto-generated dev key | Required in `.env` |
| Network | localhost only (127.0.0.1) | Tailscale VPN (0.0.0.0 + UFW) |
| Worker | `python scripts/run_huey_worker.py` | systemd `ivt-worker.service` |
| Database | SQLite with WAL | Same, with daily backups |
| Logging | Console via structlog (DEBUG level) | Structured JSON to file via structlog (INFO level) |
| Process mgmt | Manual (Ctrl+C) | systemd (auto-restart) |

### Tailscale Network Setup

The application relies on Tailscale for all production network access. Tailscale creates a zero-trust mesh VPN using WireGuard encryption, meaning every connection between your devices is end-to-end encrypted. No port forwarding, no dynamic DNS, and no exposure to the public internet.

#### Why Tailscale

- **Zero-trust networking**: every device authenticates individually; there is no trusted LAN.
- **WireGuard-based encryption**: all traffic is encrypted in transit with modern, audited cryptography.
- **No port forwarding**: the server does not need any ports open to the internet. Your router firewall stays closed.
- **Network-level authentication**: only devices authenticated to your tailnet can reach the server. User identity for audit logging is trust-based (`X-Username` header set by the client).
- **Free tier**: a single-user Tailscale account is free and sufficient for this application.

#### Installation

```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Authenticate (opens a browser window for login)
sudo tailscale up

# Verify your Tailscale IP
tailscale ip -4
```

#### MagicDNS

Once Tailscale is running, you can access the app using a human-readable hostname instead of memorizing IP addresses:

```
http://<hostname>.<tailnet-name>.ts.net:8050
```

MagicDNS is enabled by default on most Tailscale accounts. Check your admin console at https://login.tailscale.com if DNS resolution is not working.

#### Firewall Lockdown

Even though the app binds to `0.0.0.0` in production (so it listens on all interfaces), UFW ensures that only traffic arriving over the Tailscale interface can reach it:

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

With these rules in place, port 8050 is unreachable from the local network or the internet. Only devices authenticated to your Tailscale tailnet can connect.

#### How User Identity Works

1. A user connects to the app through Tailscale (only authenticated tailnet members can reach the server).
2. The app reads the `X-Username` header from each request for audit logging.
3. This header is **trust-based**: the client sets it, and the app records the value. Tailscale provides network-level authentication (ensuring only authorized devices connect), but does not automatically inject identity headers.
4. No passwords or sessions are needed -- access control comes from the network layer.

### Production Deployment

#### 1. Environment Setup

```bash
# Create and configure .env from the provided template
cp .env.example .env

# Generate a SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"

# Edit .env and set at minimum:
#   FLASK_ENV=production
#   SECRET_KEY=<paste the generated key>
#   IVT_SIGNING_KEY=<generate another key the same way>
#   HOST=0.0.0.0
#   DEBUG=false
#   Optional: IVT_ACCESS_PIN=<your-pin>
```

The `EnvironmentFile` directive in `ivt-app.service` loads these variables at service start. The leading `-` in the directive means the service will not fail if the file is missing (but production should always have one).

#### 2. Initialize Database

```bash
source ~/miniconda3/etc/profile.d/conda.sh
conda activate IVT_K
python scripts/init_db.py
```

This runs any pending Alembic migrations. If the database does not exist yet, it falls back to `db.create_all()` and stamps the Alembic head.

#### 3. Install systemd Services

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

#### 4. Verify

```bash
# Check that the app and worker are running
systemctl status ivt-app ivt-worker

# Confirm the timers are scheduled
systemctl list-timers | grep ivt

# Hit the health endpoint
curl -s http://localhost:8050/api/health
```

### Service Architecture

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

- **ivt-app** and **ivt-worker** are long-running (`Type=simple`). systemd restarts them automatically if they crash (`Restart=always`).
- **ivt-backup** and **ivt-inactivity-check** are oneshot services triggered by their respective timers. They run once and exit.
- The worker depends on the app (`Requires=ivt-app.service`), so starting the worker will also start the app if it is not already running.

Resource limits are defined in the service files to prevent runaway processes:

- **ivt-app.service**: `MemoryMax=4G`, `CPUQuota=200%`
- **ivt-worker.service**: `MemoryMax=8G`, `CPUQuota=400%`

### Alternative: Gunicorn

A WSGI entry point is available at `wsgi.py` for use with Gunicorn or other WSGI servers:

```bash
# -w 1 is required: Dash stores callback state in-process and is not safe for multiple workers.
gunicorn -w 1 -b 0.0.0.0:8050 wsgi:server
```

The systemd services use `run.py` directly, but Gunicorn may be preferred for some deployment scenarios.

### Backup & Recovery

#### Automated Daily Backups

The `ivt-backup.timer` triggers a backup every day at midnight. Old backups are pruned automatically (30-day retention by default).

#### Manual Backup

```bash
# Create a backup and clean up old ones
python scripts/backup.py --cleanup

# Or trigger via systemd
sudo systemctl start ivt-backup.service
```

#### Restore from Backup

```bash
# List available backups
python scripts/backup.py --list

# Restore a specific backup
python scripts/backup.py --restore backup_2026-01-15_00-00-00.tar.gz
```

#### Project Archival

```bash
# Archive an inactive project
python scripts/archive_project.py archive 123 --name "Project Name"

# Restore an archived project
python scripts/archive_project.py restore 123

# List all archives
python scripts/archive_project.py list

# Check archive status for a project
python scripts/archive_project.py status 123
```

Backups capture the database, project data, and configuration. They are stored as timestamped `.tar.gz` archives in the `backups/` directory with accompanying metadata JSON files.

---

## Database

### Migrations

The application uses Alembic for database schema migrations. The Alembic configuration file is at `alembic/alembic.ini`, and all commands must reference it:

```bash
# Apply all pending migrations
alembic -c alembic/alembic.ini upgrade head

# Roll back one migration
alembic -c alembic/alembic.ini downgrade -1

# Show current migration version
alembic -c alembic/alembic.ini current

# Show full migration history
alembic -c alembic/alembic.ini history

# Create a new migration from model changes
alembic -c alembic/alembic.ini revision --autogenerate -m "description"
```

#### Migration History (9 migrations)

| # | Revision | Description |
|---|----------|-------------|
| 1 | `22ec2d6034b4` | Initial schema -- all ORM models |
| 2 | `b4f2a8c91d03` | Add indexes on frequently queried foreign key columns |
| 3 | `a3b7c9e2f401` | Add AccessLog table for PIN gate audit trail |
| 4 | `d9354085474a` | Add `model_residuals` column to AnalysisVersion |
| 5 | `8ff2e5422fc8` | Add protocol history fields to ReactionSetup |
| 6 | `81915dfa5605` | Add `ligand_condition` to WellAssignment, Well, FoldChange, HierarchicalResult; add `comparison_type` to FoldChange |
| 7 | `09354998e331` | Add `plasmid_size_bp` to Construct for nM-based DNA targeting |
| 8 | `b078f506e286` | Merge divergent migration heads |
| 9 | `add_exclude_from_fc` | Add `exclude_from_fc` column for fold-change exclusion ¹ |

¹ Migration 9 uses a human-readable slug as its revision ID rather than the standard hex hash.

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
- SQLite does not support `ALTER COLUMN`. Review autogenerated migrations and remove any `op.alter_column()` calls -- use batch operations instead.
- Test migrations against a copy of the production database before applying.
- WAL mode is enabled automatically during initialization.

---

## Project Structure

```
IVT_KINETICS_ANALYZER/
├── app/                        # Main application package
│   ├── __init__.py             # Application factory (6 staged helpers)
│   ├── config.py               # Configuration classes (Dev, Prod, Testing)
│   ├── errors.py               # ServiceError exception hierarchy
│   ├── extensions.py           # Flask extensions (SQLAlchemy, CSRF)
│   ├── models/                 # SQLAlchemy ORM models (33 models + 1 abstract base, 14 enums) ¹
│   ├── services/               # Business logic layer (34 services: 3 facades + 31 implementations)
│   ├── api/                    # REST API blueprints (10 blueprints + auth gate) ¹
│   ├── layouts/                # Dash page layouts (27: 20 top-level + 7 in analysis_results/)
│   ├── callbacks/              # Dash callbacks (29: 3 facades + 12 sub-modules + 14 standalone) ¹
│   ├── components/             # 16 reusable UI components (forest plot, violin plot, plate heatmap, Q-Q plot, etc.)
│   ├── analysis/               # Scientific computation (curve fitting, Bayesian, Frequentist)
│   ├── calculator/             # Reaction/dilution calculators, DNA converter
│   ├── schemas/                # Pydantic request/response validation schemas
│   ├── parsers/                # BioTek file parser
│   ├── tasks/                  # Huey background task configuration
│   └── utils/                  # Shared utilities (validation, transactions, error capture)
├── plugins/                    # Plugin directory
│   └── kinetic_models/         # Custom kinetic model plugins (1 example)
├── scripts/                    # Utility scripts (9 scripts) ¹
├── tests/                      # Test suite (84 files: 76 unit + 2 integration + 4 workflow + 2 statistical + 2 fixtures; 2524 tests) ¹
├── alembic/                    # Database migrations (9 migrations)
│   ├── alembic.ini             # Alembic configuration
│   └── versions/               # Migration scripts
├── deploy/                     # Deployment configuration (systemd services + timers)
├── data/                       # Project data (created at runtime)
├── logs/                       # Application logs (created at runtime)
├── .env.example                # Environment variable template
└── run.py                      # Application entry point
```

¹ *Component counts verified February 2026. Counts may drift as features are added.*

---

## Architecture

### Application Structure

The application uses a **Flask backend** with a **Dash frontend** mounted on the Flask server. It follows the **application factory pattern** with `create_app()` in `app/__init__.py`, decomposed into six staged initialization helpers:

1. `_setup_logging` -- configure console and file logging based on environment
2. `_validate_and_init` -- validate configuration, initialize SQLAlchemy and CSRF protection
3. `_discover_plugins` -- scan `plugins/kinetic_models/` and register custom models
4. `_register_middleware` -- set up request middleware (rate limiting, audit logging, user identity)
5. `_register_api_blueprints` -- import and register all 10 API blueprints, exempt from CSRF
6. `_setup_dash_app` -- create the Dash application, set layout, register all callbacks

The frontend uses **Dash Mantine Components** (`dash-mantine-components`) for all UI elements, with **Dash Iconify** for icons and **Plotly** for all interactive visualizations.

A separate `create_worker_app()` builds a lightweight Flask+SQLAlchemy context for the Huey worker without loading Dash or callbacks.

Three configuration classes in `app/config.py` control behavior: `DevelopmentConfig`, `ProductionConfig`, and `TestingConfig`.

### Service Layer

The 34 services are organized into focused responsibilities with three facade patterns for backwards compatibility:

- **ComparisonService** (facade) delegates to `FoldChangeService`, `ComparisonGraphService`, `PrecisionWeightService`
- **FittingService** (facade) delegates to `FitComputationService`, `FoldChangeCalculationService`, `FitManagementService`
- **ExportService** (facade) delegates to `ProtocolExportService`, `FigureExportService`, `DataExportService`

### Callback Layer

The 29 callback files follow the same facade decomposition for the three largest modules:

- **analysis_callbacks.py** (facade) delegates to `analysis_version_callbacks`, `analysis_visualization_callbacks`, `analysis_execution_callbacks`, `analysis_comparison_callbacks`, `analysis_fitting_callbacks` + `analysis_utils`
- **layout_callbacks.py** (facade) delegates to `layout_grid_callbacks`, `layout_assignment_callbacks` + `layout_utils`
- **upload_callbacks.py** (facade) delegates to `upload_form_callbacks`, `upload_processing_callbacks` + `upload_utils`

### Analysis Pipeline

1. **Upload** -- BioTek plate reader files are parsed (`app/parsers/biotek_parser.py`), wells matched to layout assignments
2. **QC Flagging** -- automatic detection of outliers, signal saturation, temperature drift, and background instability
3. **Curve Fitting** -- least-squares fitting of 5 built-in kinetic models to all wells:
   - `plateau` -- simple saturation curve (F_baseline, F_max, k)
   - `delayed_exponential` -- exponential rise with lag phase (F_baseline, F_max, k_obs, t_lag)
   - `logistic` -- sigmoidal growth curve (F_baseline, F_max, k, t_mid)
   - `double_exponential` -- biphasic kinetics with two rate constants (F_baseline, A1, k1, A2, k2)
   - `linear_initial_rate` -- linear initial rate with lag (F_baseline, v_init, t_lag)
4. **Dual Statistical Analysis** -- always runs both methods:
   - **Bayesian**: PyMC hierarchical models with MCMC sampling, per-family variance components, R-hat convergence diagnostics
   - **Frequentist**: statsmodels mixed-effects models with REML estimation, Wald confidence intervals
5. **Fold-Change Comparisons** -- within-condition and ligand-effect fold changes with variance inflation factors (1.0, sqrt(2), 2.0, 4.0)
6. **Export** -- publication packages with raw data, MCMC traces, model diagnostics, and validation certificates

### Background Tasks (Huey)

Long-running computations run in a Huey task queue with an SQLite backend and a single worker process. Five task types are supported:

- `CURVE_FITTING` -- batch curve fitting with parallelization
- `MCMC_SAMPLING` -- MCMC sampling with checkpointing on failure
- `DATA_EXPORT` -- publication package and data export
- `PACKAGE_VALIDATION` -- publication package integrity validation
- `BATCH_PROCESSING` -- generic batch processing

Tasks report progress to `TaskProgress` records polled by the frontend. MCMC analysis checkpoints on failure for debugging and resumption. The worker uses `create_worker_app()` for a lightweight Flask context.

### Security Model

- **Network isolation**: production access exclusively via Tailscale VPN. UFW blocks all traffic not arriving over the `tailscale0` interface.
- **User identity**: access control is handled at the network layer (only Tailscale-authenticated devices can connect). The app reads a trust-based `X-Username` header for audit logging. No passwords are stored.
- **Optional PIN gate**: set `IVT_ACCESS_PIN` for an additional access control layer on top of Tailscale.
- **CSRF protection**: Flask-WTF protects all Flask routes. Dash internal callback routes are exempt (they use their own request validation).
- **Rate limiting**: 100/min for reads, 30/min for writes, 20/min for uploads, 5/min for analysis endpoints.
- **Payload limits**: 10 MB max request size, 100K character string limit.
- **PIN hardening**: constant-time comparison via HMAC-SHA256, session regeneration after login (anti-fixation), rate-limited attempts.
- **Username sanitization**: max 64 characters, alphanumeric + underscore/hyphen/dot only, control characters stripped.
- **Production key validation**: startup check rejects known insecure SECRET_KEY values (e.g., "change-me", "secret").
- **Service hardening**: all systemd services run with `NoNewPrivileges=true`, `ProtectSystem=strict`, `ProtectHome=read-only`, and `PrivateTmp=true`. Write access is limited to the application directory via `ReadWritePaths`.

---

## Scripts & Utilities

### Database Management

| Script | Description |
|--------|-------------|
| `python scripts/init_db.py` | Initialize or upgrade the database (runs Alembic migrations, falls back to `create_all`) |
| `python scripts/init_db.py --reset` | Wipe database and recreate from scratch |
| `python scripts/init_db.py --nuke` | Complete reset: wipe database, uploads, traces, checkpoints, and logs (prompts for confirmation) |

### Application

| Script | Description |
|--------|-------------|
| `python run.py` | Start web application (add `--production --host 0.0.0.0` for production) |
| `python scripts/run_huey_worker.py` | Start background task worker (required for MCMC analysis) |

### Data Management

| Script | Description |
|--------|-------------|
| `python scripts/seed_data.py [--full] [--clean] [-v]` | Seed sample data for development |
| `python scripts/backup.py [--cleanup] [--list] [--restore FILE]` | Create, list, or restore backups |
| `python scripts/archive_project.py {archive\|restore\|list\|status}` | Archive and restore inactive projects |

### Maintenance

| Script | Description |
|--------|-------------|
| `python scripts/check_inactive_projects.py [--warn] [--json] [--threshold DAYS]` | Monitor projects inactive for 6+ months (default: 180 days, configurable via `--threshold`) |
| `python scripts/repair_deleted_constructs.py` | Fix soft-deleted construct identifiers |

### Environment

| Script | Description |
|--------|-------------|
| `bash scripts/setup_environment.sh` | Create/update conda environment with system library installation (Kaleido, WeasyPrint dependencies) |

### Validation

| Script | Description |
|--------|-------------|
| `python scripts/run_statistical_validation.py [--test NAME] [--list]` | Run statistical validation suite (coverage, bias, calibration) |

---

## Key Dependencies

| Category | Packages |
|----------|----------|
| **Web** | Flask, Dash 4.0+, Dash Mantine Components, Dash Iconify |
| **Database** | SQLAlchemy, Flask-SQLAlchemy, Alembic |
| **Scientific** | NumPy, SciPy, Pandas |
| **Statistics** | PyMC (Bayesian MCMC), statsmodels (Frequentist REML), ArviZ (diagnostics) |
| **Visualization** | Plotly, Kaleido (static export) |
| **Export** | WeasyPrint (PDF), xarray + h5netcdf (NetCDF traces), openpyxl (Excel) |
| **Infrastructure** | Huey (task queue), structlog (logging), Pydantic (validation), Flask-WTF (CSRF) |

Full dependency lists: `requirements.txt` (production) and `requirements-dev.txt` (development). Conda users: `environment.yml`.

---

## API Documentation

The REST API is documented with OpenAPI 3.0:

- **Swagger UI**: http://localhost:8050/api/docs
- **ReDoc**: http://localhost:8050/api/redoc
- **OpenAPI JSON**: http://localhost:8050/api/openapi.json

### Key Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/projects/` | List all projects |
| `POST /api/projects/` | Create new project |
| `GET /api/projects/{id}/analysis` | Get analysis results |
| `GET /api/tasks/{id}` | Get background task progress |
| `POST /api/calculator/mastermix` | Calculate master mix |
| `POST /api/smart-planner/suggest` | Get experiment suggestions |

User identification for audit logging uses a trust-based `X-Username` header (defaults to `anonymous` if not set).

---

## Plugin System

Custom kinetic models can be added via the plugin system. Place Python files in `plugins/kinetic_models/`:

```python
from app.analysis.kinetic_models import KineticModel, kinetic_model, ModelParameters

@kinetic_model
class MyCustomModel(KineticModel):
    @property
    def name(self) -> str:
        return "my_custom_model"

    @property
    def param_names(self) -> list[str]:
        return ["F0", "F_max", "k_obs", "k_extra"]

    def evaluate(self, t: np.ndarray, params: ModelParameters) -> np.ndarray:
        F0 = params["F0"]
        F_max = params["F_max"]
        k_obs = params["k_obs"]
        k_extra = params["k_extra"]
        return F0 + F_max * (1 - np.exp(-k_obs * t)) + k_extra * t

    def initial_guess(self, t: np.ndarray, F: np.ndarray) -> ModelParameters:
        # Estimate initial parameters from raw data
        ...

    def get_visualization_config(self) -> dict[str, Any]:
        # Configure plots and derived metrics
        ...
```

Plugins are automatically discovered and loaded at application startup. One example plugin (`example_biexponential.py`) is included, implementing a 4-parameter biexponential model with photobleaching correction (F0, F_max, k_obs, k_bleach).

---

## Testing

The test suite contains 84 test files (2524 individual tests) organized into five categories:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=app

# Run specific test categories
pytest tests/unit/               # 76 unit test files
pytest tests/integration/        # 2 integration test files (API endpoints)
pytest tests/workflows/          # 4 workflow test files (multi-step API flows)
pytest tests/statistical_validation/  # 2 statistical validation files (coverage, bias)

# Run a single test file
pytest tests/unit/test_curve_fitting.py

# Run tests matching a pattern
pytest -k "test_bayesian"
```

### Test Fixtures

Shared factory functions live in `tests/fixtures/` (2 files):

- `project_fixtures.py` -- `create_test_project`, `create_test_construct`, `create_test_session`, `create_test_plate`, `create_test_well`, `create_test_project_with_constructs`, `create_test_project_with_wells`
- `analysis_fixtures.py` -- `create_test_fit_result`, `create_test_fold_change`, `create_test_analysis_version`, `create_test_hierarchical_result`

Key fixtures in `tests/conftest.py`:

- `app` -- Application instance with test configuration
- `db_session` -- Database session with automatic cleanup
- `test_project` -- Factory for creating test projects
- `temp_data_dir` -- Temporary directory for test files

---

## Code Quality

```bash
# Lint check
ruff check .

# Auto-fix lint issues
ruff check --fix .

# Format code
ruff format .

# Type checking
mypy app
```

### Pre-commit Hooks

```bash
# Install pre-commit hooks (runs ruff check + format on staged files)
pip install pre-commit
pre-commit install
```

---

## Health Checks

- `GET /api/health` -- Full health check (database connectivity, Huey worker state, disk usage)
- `GET /api/health/live` -- Liveness probe (returns 200 if the process is running)
- `GET /api/health/ready` -- Readiness probe (returns 200 if all dependencies are available)
- `GET /api/health/timeouts` -- Operation timeout configuration

---

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

### Database Locked Errors

If you see "database is locked" errors, the WAL file may need checkpointing:

```bash
# Stop both services
sudo systemctl stop ivt-app ivt-worker

# Force a WAL checkpoint
sqlite3 ivt_kinetics.db "PRAGMA wal_checkpoint(TRUNCATE);"

# Restart services
sudo systemctl start ivt-app ivt-worker
```

### MCMC Out of Memory

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

### View Logs

```bash
# Application logs (systemd)
sudo journalctl -u ivt-app -f

# Worker logs
sudo journalctl -u ivt-worker -f

# Backup logs
sudo journalctl -u ivt-backup -n 50

# Inactivity check results
sudo journalctl -u ivt-inactivity-check -n 50

# JSON application logs
tail -f logs/app.jsonl | python -m json.tool
```

---

## Scientific Background

The application analyzes IVT kinetics using:

- **Plate Formats**: 96-well or 384-well (checkerboard pattern for 384 to prevent signal bleed)
- **Anchor Constructs**: Each plate requires wild-type (WT), unregulated (reporter-only), and negative control
- **Ligand Levels**: Binary (0 vs max concentration) for activation studies
- **Comparison Hierarchy**: Primary (mutant vs WT) -> Secondary (WT vs unregulated) -> Tertiary (derived)
- **Variance Inflation Factors**: 1.0 (direct), sqrt(2) (one-hop), 2.0 (two-hop), 4.0 (cross-family)
- **Ligand Condition Pipeline**: Full +Lig/-Lig experimental design with within-condition and ligand-effect fold-change comparisons
- **Per-Family Models**: Independent hierarchical models per T-box family with family-specific variance components

---

## License

MIT License -- see LICENSE file for details.

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Run tests (`pytest`)
4. Run linting (`ruff check . && ruff format .`)
5. Commit changes (`git commit -m 'Add amazing feature'`)
6. Push to branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

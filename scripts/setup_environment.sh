#!/usr/bin/env bash
# ==============================================================================
# IVT Kinetics Analyzer — Environment Setup Script
#
# Creates (or updates) the IVT_K conda environment with all dependencies
# required to run and develop this project, including system libraries needed
# by Kaleido (Plotly image export) and WeasyPrint (PDF generation).
#
# Usage:
#   bash scripts/setup_environment.sh              # full setup (create + dev)
#   bash scripts/setup_environment.sh --update     # update existing environment
#   bash scripts/setup_environment.sh --no-dev     # skip dev/testing packages
#   bash scripts/setup_environment.sh --skip-sys   # skip system library install
#   bash scripts/setup_environment.sh --help       # show this help
#
# Flags can be combined:
#   bash scripts/setup_environment.sh --update --no-dev --skip-sys
# ==============================================================================
set -euo pipefail

ENV_NAME="IVT_K"
PYTHON_VERSION="3.11"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ---------- helpers -----------------------------------------------------------

info()  { echo -e "\033[1;34m[INFO]\033[0m  $*"; }
ok()    { echo -e "\033[1;32m[OK]\033[0m    $*"; }
warn()  { echo -e "\033[1;33m[WARN]\033[0m  $*"; }
err()   { echo -e "\033[1;31m[ERROR]\033[0m $*"; exit 1; }

usage() {
    sed -n '2,/^# =====/{ /^# /s/^# //p }' "$0"
    exit 0
}

# ---------- parse arguments ---------------------------------------------------

UPDATE_MODE=false
INSTALL_DEV=true
INSTALL_SYSTEM_DEPS=true

while [[ $# -gt 0 ]]; do
    case "$1" in
        --update)     UPDATE_MODE=true ;;
        --no-dev)     INSTALL_DEV=false ;;
        --skip-sys)   INSTALL_SYSTEM_DEPS=false ;;
        --help|-h)    usage ;;
        *)            err "Unknown flag: $1  (use --help for usage)" ;;
    esac
    shift
done

# ---------- preflight checks --------------------------------------------------

if ! command -v conda &>/dev/null; then
    err "conda not found. Install Miniconda/Anaconda first:\n  https://docs.conda.io/en/latest/miniconda.html"
fi

# Source conda shell functions so 'conda activate' works in scripts
CONDA_BASE="$(conda info --base)"
source "$CONDA_BASE/etc/profile.d/conda.sh"

# ---------- create or verify environment --------------------------------------

if conda env list | grep -qw "$ENV_NAME"; then
    if $UPDATE_MODE; then
        info "Updating existing '$ENV_NAME' environment"
    else
        info "Environment '$ENV_NAME' already exists — updating in place"
        info "  (pass --update to suppress this message)"
    fi
else
    info "Creating conda environment '$ENV_NAME' (Python $PYTHON_VERSION) ..."
    conda create -y -n "$ENV_NAME" python="$PYTHON_VERSION" -c conda-forge
    ok "Environment created"
fi

# Temporarily disable nounset — conda's activation/deactivation hooks
# reference variables (e.g. CONDA_BACKUP_CXX) that may be unset.
set +u
conda activate "$ENV_NAME"
set -u

# ---------- conda-forge packages (compiled / low-level) -----------------------
# These benefit from conda's binary builds — BLAS, compilers, C extensions.
# Pinned to the versions used in the reference IVT_K environment.

info "Installing conda-forge packages ..."
conda install -y -c conda-forge \
    python="$PYTHON_VERSION" \
    numpy \
    scipy \
    pandas \
    statsmodels \
    plotly \
    python-kaleido \
    flask \
    flask-wtf \
    werkzeug \
    orjson \
    pytest \
    pytest-timeout

ok "Conda-forge packages installed"

# ---------- pip production dependencies ---------------------------------------
# pip handles Dash ecosystem, PyMC/ArviZ stack, PDF tools, and utilities
# better than conda due to faster resolution and broader availability.

info "Installing pip production dependencies ..."
pip install --upgrade \
    "dash>=4.0.0" \
    "dash-mantine-components>=2.5.0" \
    "dash-iconify>=0.1.2" \
    "flask-sqlalchemy>=3.1.0" \
    "sqlalchemy>=2.0.0" \
    "alembic>=1.18.0" \
    "huey>=2.6.0" \
    "pymc>=5.27.0" \
    "arviz>=0.23.0" \
    "xarray" \
    "joblib>=1.5.0" \
    "structlog>=25.0.0" \
    "openpyxl>=3.1.0" \
    "pydantic>=2.12.0" \
    "python-dotenv>=1.2.0" \
    "weasyprint>=68.1" \
    "reportlab>=4.0"

ok "Production dependencies installed"

# ---------- pip development dependencies (optional) ---------------------------

if $INSTALL_DEV; then
    info "Installing pip development dependencies ..."
    pip install --upgrade \
        "pytest-cov>=7.0.0" \
        "pytest-mock>=3.15.0" \
        "ruff>=0.14.0" \
        "mypy>=1.19.0" \
        "pre-commit>=4.5.0" \
        "pandas-stubs>=2.3.0" \
        "types-requests>=2.32.0" \
        "watchdog>=6.0.0"
    ok "Development dependencies installed"
else
    info "Skipping dev dependencies (--no-dev)"
fi

# ---------- system libraries (Kaleido + WeasyPrint) ---------------------------
# Kaleido >= 1.0 uses choreographer which needs Chrome/Chromium system libs.
# WeasyPrint needs Pango, Cairo, GDK-PixBuf for HTML-to-PDF rendering.

if $INSTALL_SYSTEM_DEPS; then
    info "Checking system libraries for Kaleido (Chrome) and WeasyPrint (Pango/Cairo) ..."

    # libasound2 was renamed to libasound2t64 in Ubuntu 24.04+
    if apt-cache show libasound2t64 &>/dev/null 2>&1; then
        ALSA_PKG="libasound2t64"
    else
        ALSA_PKG="libasound2"
    fi

    # Chrome deps (Kaleido figure export: PNG/SVG/PDF from Plotly)
    CHROME_DEPS="libnss3 libatk-bridge2.0-0 libcups2 libxcomposite1 \
libxdamage1 libxfixes3 libxrandr2 libgbm1 libxkbcommon0 $ALSA_PKG"

    # WeasyPrint deps (HTML/CSS to PDF rendering)
    WEASYPRINT_DEPS="libpango-1.0-0 libpangocairo-1.0-0 libpangoft2-1.0-0 \
libcairo2 libgdk-pixbuf-2.0-0 libffi-dev libharfbuzz0b libfontconfig1 libfreetype6"

    ALL_DEPS="$CHROME_DEPS $WEASYPRINT_DEPS"

    if ! command -v apt-get &>/dev/null; then
        warn "apt-get not found — skipping automatic system dependency install."
        warn "Install these packages for your distro:"
        warn "  Chrome/Kaleido: $CHROME_DEPS"
        warn "  WeasyPrint:     $WEASYPRINT_DEPS"
    elif sudo -n true 2>/dev/null; then
        sudo apt-get update -qq
        # shellcheck disable=SC2086
        if sudo apt-get install -y $ALL_DEPS; then
            ok "System dependencies installed"
        else
            warn "Some system packages failed to install — see output above."
            warn "Figure export and PDF generation may not work."
        fi
    else
        warn "sudo requires a password — skipping automatic system dependency install."
        warn "Run manually:"
        warn "  sudo apt-get install -y $ALL_DEPS"
    fi
else
    info "Skipping system dependencies (--skip-sys)"
fi

# ---------- Kaleido Chrome binary ---------------------------------------------
# Kaleido 1.x bundles Chrome via choreographer. On first use it downloads a
# Chrome binary into the choreographer package directory. We trigger this now
# so the first figure export doesn't stall.

info "Verifying Kaleido figure export ..."
KALEIDO_OK=false
if python -c "
import plotly.graph_objects as go
fig = go.Figure(data=go.Bar(y=[1,2,3]))
img = fig.to_image(format='png')
assert len(img) > 0
" 2>/dev/null; then
    KALEIDO_OK=true
    ok "Kaleido figure export working"
else
    info "Downloading Chrome for Kaleido (one-time) ..."
    if python -c "
import sys
try:
    import kaleido
    kaleido.get_chrome_sync()
    print('Chrome downloaded successfully')
except Exception as e:
    print(f'Could not download Chrome: {e}', file=sys.stderr)
    sys.exit(1)
" 2>&1; then
        # Verify again after download
        if python -c "
import plotly.graph_objects as go
fig = go.Figure(data=go.Bar(y=[1,2,3]))
fig.to_image(format='png')
" 2>/dev/null; then
            KALEIDO_OK=true
            ok "Kaleido figure export working (after Chrome download)"
        fi
    fi

    if ! $KALEIDO_OK; then
        warn "Kaleido figure export is NOT working."
        warn "Figure export (PNG/SVG/PDF) will fail at runtime."
        warn "Fix: ensure Chrome system libs are installed and run:"
        warn "  python -c \"import kaleido; kaleido.get_chrome_sync()\""
    fi
fi

# ---------- WeasyPrint verification -------------------------------------------

info "Verifying WeasyPrint PDF rendering ..."
if python -c "
from weasyprint import HTML
pdf = HTML(string='<p>test</p>').write_pdf()
assert len(pdf) > 0
" 2>/dev/null; then
    ok "WeasyPrint PDF rendering working"
else
    warn "WeasyPrint PDF rendering is NOT working."
    warn "Daily report PDF export will fail at runtime."
    warn "Fix: install system libraries (libpango, libcairo, libgdk-pixbuf)"
fi

# ---------- database ----------------------------------------------------------

info "Initializing database ..."
cd "$PROJECT_DIR"
python scripts/init_db.py
ok "Database ready"

# ---------- verification summary ----------------------------------------------

info "Running import verification ..."
IMPORT_FAILURES=0
while IFS= read -r pkg; do
    if ! python -c "import $pkg" 2>/dev/null; then
        warn "  Failed to import: $pkg"
        IMPORT_FAILURES=$((IMPORT_FAILURES + 1))
    fi
done <<'PACKAGES'
dash
dash_mantine_components
dash_iconify
flask
flask_sqlalchemy
sqlalchemy
alembic
huey
numpy
scipy
pandas
statsmodels
pymc
arviz
plotly
kaleido
weasyprint
joblib
structlog
openpyxl
pydantic
xarray
PACKAGES

if [[ $IMPORT_FAILURES -eq 0 ]]; then
    ok "All production packages import successfully"
else
    warn "$IMPORT_FAILURES package(s) failed to import — check messages above"
fi

# ---------- summary -----------------------------------------------------------

echo ""
echo "============================================================"
ok "IVT_K environment is ready!"
echo ""
echo "  Activate:     conda activate $ENV_NAME"
echo "  Run app:      python run.py"
echo "  Run worker:   python scripts/run_huey_worker.py"
echo "  Run tests:    pytest"
echo "  Init DB:      python scripts/init_db.py"
echo ""
if $INSTALL_DEV; then
    echo "  Lint:         ruff check ."
    echo "  Format:       ruff format ."
    echo "  Type check:   mypy app"
    echo ""
fi
echo "============================================================"

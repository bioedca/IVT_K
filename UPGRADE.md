# Upgrade guide

How to upgrade an existing IVT_K deployment to the **reagent inventory** feature.

## Upgrading from `12559c8` → the reagent-inventory release

**What this adds.** A per-project **reagent inventory** — the stock and final
concentration of every IVT component (NTPs, DFHBI, MgCl₂, 10× buffer, and the
three enzymes) — is now first-class, user-owned data instead of hardcoded lot
defaults:

- Edit **stock + final** for every component on the project **Settings → Reagents** tab.
- Edit the four **NTP stocks** directly on the **Calculator**; they pre-fill from
  and are written back to the inventory on Calculate (kept in sync with Settings).
- Reaction-setup generation now reads every component's concentrations from the
  inventory, and buffer/MgCl₂/enzyme volumes are concentration-driven.

Delivered in PRs #7–#10 (model + seeding, concentration-driven math, the Settings
editor, and the calculator NTP inputs).

### What you need to do

This upgrade is **code + one database migration**. There are **no dependency
changes** (`requirements.txt` / `environment.yml` are unchanged), so the conda
environment does not need rebuilding.

SQLite is single-writer, so stop the writers before migrating.

1. **Stop the app and worker** (so nothing writes during the migration):

   ```bash
   # systemd production example
   sudo systemctl stop ivt-app ivt-worker
   # or just stop the `gunicorn ... wsgi:server` and `run_huey_worker.py` processes
   ```

2. **Get the new code.** The feature is included as of commit `7ca64f6` (the
   merge of PR #10), so any `main` at or after that commit has it. Pull the
   release, or check out that exact commit for a reproducible upgrade:

   ```bash
   git -C /path/to/IVT_K pull --ff-only origin main
   # or pin to the exact release commit:
   # git -C /path/to/IVT_K checkout 7ca64f6
   ```

3. **Apply the database migration.** A new Alembic migration
   (`f1a2b3c4d5e6`, revises `d7e3b9c4f812`) creates the `reagent_inventories`
   table. `init_db.py` runs `alembic upgrade head` and is idempotent:

   ```bash
   conda activate IVT_K          # if not already active
   python scripts/init_db.py
   ```

4. **Restart the app and worker:**

   ```bash
   sudo systemctl start ivt-app ivt-worker
   # or run the two processes yourself (in separate terminals):
   #   gunicorn -w 1 -b 0.0.0.0:8050 wsgi:server
   #   python scripts/run_huey_worker.py
   ```

That's it. See [DEPLOYMENT.md](DEPLOYMENT.md) for the general run/migrate commands.

### No data migration is required

Existing projects do **not** need a data backfill. Each project's inventory row
is created lazily with the standard defaults the first time it is read (the
Settings tab, the calculator, or a reaction-setup calculation), via
`ReagentInventoryService.get_or_create`.

### Behavior is unchanged at the defaults

The seeded defaults equal the values the calculator used before this release, so
**existing reaction setups compute identically** until you deliberately change a
concentration. The enzyme volumes were converted from a fixed `V_rxn × factor /
200` ratio to true concentration math (`V = C_final × V_rxn / C_stock`), which is
exactly equivalent at the default stock/final concentrations.

### Verifying the upgrade

- Open any project → **Settings → Reagents**: every component shows its stock and
  final concentration (defaults, or your edits).
- Open the project **Calculator**: the **NTP stock concentrations** block is
  pre-filled; editing a value and clicking **Calculate** saves it back to the
  inventory (visible afterwards on the Settings tab).

### Rolling back

If you need to revert to `12559c8`:

```bash
python -m alembic -c alembic/alembic.ini downgrade d7e3b9c4f812   # drops reagent_inventories
git -C /path/to/IVT_K checkout 12559c8
```

> Downgrading drops the `reagent_inventories` table, discarding any reagent
> concentrations you entered. Calculations revert to the previous hardcoded
> defaults, so saved protocols are unaffected.

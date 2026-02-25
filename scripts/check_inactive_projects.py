#!/usr/bin/env python3
"""
Inactive Project Check Script.

Phase H.3: Inactivity flagging for projects inactive > 6 months.

This script should be run periodically (e.g., weekly via cron) to:
1. Identify projects approaching inactivity threshold
2. Send warnings for projects at 5 months of inactivity
3. Flag projects at 6 months for archival consideration

Usage:
    python scripts/check_inactive_projects.py           # Check and report
    python scripts/check_inactive_projects.py --warn    # Send warnings
    python scripts/check_inactive_projects.py --json    # Output as JSON
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


def get_inactive_projects():
    """Get list of inactive projects."""
    from app import create_app
    from app.services.project_storage_service import ProjectStorageService

    app = create_app()
    with app.server.app_context():
        return ProjectStorageService.get_inactive_projects()


def get_projects_needing_warning():
    """Get projects approaching inactivity that need warning."""
    from app import create_app
    from app.services.project_storage_service import ProjectStorageService

    app = create_app()
    with app.server.app_context():
        return ProjectStorageService.get_projects_needing_warning()


def mark_warnings_sent(project_ids: list):
    """Mark warnings as sent for projects."""
    from app import create_app
    from app.services.project_storage_service import ProjectStorageService

    app = create_app()
    with app.server.app_context():
        for project_id in project_ids:
            ProjectStorageService.mark_warning_sent(project_id)


def generate_report(inactive: list, needing_warning: list, as_json: bool = False):
    """Generate a report of inactive projects."""
    report = {
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "inactive_count": len(inactive),
            "warning_count": len(needing_warning),
        },
        "inactive_projects": inactive,
        "projects_needing_warning": needing_warning
    }

    if as_json:
        print(json.dumps(report, indent=2))
    else:
        print("\n" + "=" * 60)
        print("INACTIVE PROJECT REPORT")
        print(f"Generated: {report['generated_at']}")
        print("=" * 60)

        print(f"\nInactive Projects (6+ months): {len(inactive)}")
        if inactive:
            for p in inactive:
                print(f"  - [{p['id']}] {p['name']}")
                print(f"    Last activity: {p['last_activity']}")
                print(f"    Days inactive: {p['days_inactive']}")

        print(f"\nProjects Needing Warning (5+ months): {len(needing_warning)}")
        if needing_warning:
            for p in needing_warning:
                print(f"  - [{p['id']}] {p['name']}")
                print(f"    Days inactive: {p['days_inactive']}")
                print(f"    Days until inactive threshold: {p['days_until_inactive']}")

        print("\n" + "=" * 60)

    return report


def send_warnings(projects: list):
    """
    Send inactivity warnings for projects.

    In a production system, this would send emails or create notifications.
    For now, it logs to stdout and marks warnings as sent.
    """
    if not projects:
        print("No projects need warnings.")
        return

    print(f"\nSending warnings for {len(projects)} projects:")
    for p in projects:
        print(f"  - [{p['id']}] {p['name']}: WARNING - Project will be flagged as inactive in {p['days_until_inactive']} days")

    # Mark warnings as sent
    project_ids = [p['id'] for p in projects]
    mark_warnings_sent(project_ids)
    print(f"\nMarked {len(project_ids)} projects as warned.")


def main():
    parser = argparse.ArgumentParser(
        description="Check for inactive projects and optionally send warnings."
    )
    parser.add_argument(
        "--warn",
        action="store_true",
        help="Send warnings for projects approaching inactivity"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=180,
        help="Inactivity threshold in days (default: 180)"
    )

    args = parser.parse_args()

    try:
        # Get inactive projects
        inactive = get_inactive_projects()
        needing_warning = get_projects_needing_warning()

        # Generate report
        generate_report(inactive, needing_warning, as_json=args.json)

        # Send warnings if requested
        if args.warn:
            send_warnings(needing_warning)

        # Exit with code based on findings
        if inactive:
            sys.exit(1)  # Non-zero if there are inactive projects
        sys.exit(0)

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

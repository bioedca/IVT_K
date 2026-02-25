#!/usr/bin/env python3
"""
Backup script for IVT Kinetics Analyzer.

Phase 11.5-11.6: Automated Backup System (F11.5-F11.6)

Features:
- Creates timestamped backup archives
- Checkpoints SQLite WAL before backup
- Supports configurable retention policy
- Includes database, project data, and configuration

Usage:
    python scripts/backup.py                    # Create backup
    python scripts/backup.py --cleanup          # Create backup and cleanup old ones
    python scripts/backup.py --list             # List existing backups
    python scripts/backup.py --restore <file>   # Restore from backup
"""
import os
import sys
import argparse
import tarfile
import sqlite3
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Tuple
import json
import hashlib

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class BackupManager:
    """Manages database and file backups."""

    DEFAULT_RETENTION_DAYS = 30
    BACKUP_PREFIX = "backup_"
    BACKUP_EXTENSION = ".tar.gz"

    def __init__(
        self,
        base_dir: Path,
        backup_dir: Optional[Path] = None,
        db_path: Optional[Path] = None,
        retention_days: int = DEFAULT_RETENTION_DAYS,
    ):
        """
        Initialize backup manager.

        Args:
            base_dir: Application base directory
            backup_dir: Directory for backups (default: base_dir/backups)
            db_path: Path to SQLite database (default: base_dir/ivt_kinetics.db)
            retention_days: Days to retain backups
        """
        self.base_dir = Path(base_dir)
        self.backup_dir = Path(backup_dir) if backup_dir else self.base_dir / "backups"
        self.db_path = Path(db_path) if db_path else self.base_dir / "ivt_kinetics.db"
        self.retention_days = retention_days

        # Ensure backup directory exists
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def checkpoint_database(self) -> bool:
        """
        Checkpoint SQLite WAL to ensure consistent backup.

        Returns:
            True if checkpoint successful
        """
        if not self.db_path.exists():
            print(f"Database not found: {self.db_path}")
            return False

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()

            # Force WAL checkpoint
            cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            result = cursor.fetchone()

            conn.close()

            if result[0] == 0:
                print("Database checkpoint completed successfully")
                return True
            else:
                print(f"Checkpoint returned: {result}")
                return True  # May still be okay

        except Exception as e:
            print(f"Checkpoint failed: {e}")
            return False

    def create_backup(self, include_logs: bool = False) -> Tuple[Optional[Path], dict]:
        """
        Create a full backup archive.

        Args:
            include_logs: Whether to include log files

        Returns:
            Tuple of (backup_path, metadata_dict)
        """
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_name = f"{self.BACKUP_PREFIX}{timestamp}{self.BACKUP_EXTENSION}"
        backup_path = self.backup_dir / backup_name

        metadata = {
            "timestamp": timestamp,
            "created_at": datetime.now().isoformat(),
            "base_dir": str(self.base_dir),
            "files": [],
            "total_size": 0,
            "compressed_size": 0,
        }

        # Checkpoint database first
        self.checkpoint_database()

        try:
            with tarfile.open(backup_path, "w:gz") as tar:
                # Add database file
                if self.db_path.exists():
                    tar.add(self.db_path, arcname="ivt_kinetics.db")
                    metadata["files"].append({
                        "path": "ivt_kinetics.db",
                        "size": self.db_path.stat().st_size,
                        "sha256": self._compute_file_hash(self.db_path),
                    })
                    metadata["total_size"] += self.db_path.stat().st_size

                # Add Huey database if exists
                huey_db = self.base_dir / "huey.db"
                if huey_db.exists():
                    tar.add(huey_db, arcname="huey.db")
                    metadata["files"].append({
                        "path": "huey.db",
                        "size": huey_db.stat().st_size,
                    })
                    metadata["total_size"] += huey_db.stat().st_size

                # Add data directory
                data_dir = self.base_dir / "data"
                if data_dir.exists():
                    for file_path in data_dir.rglob("*"):
                        if file_path.is_file():
                            arcname = str(file_path.relative_to(self.base_dir))
                            tar.add(file_path, arcname=arcname)
                            metadata["files"].append({
                                "path": arcname,
                                "size": file_path.stat().st_size,
                            })
                            metadata["total_size"] += file_path.stat().st_size

                # Add config files
                for config_file in ["config.py", ".env", "pyproject.toml"]:
                    config_path = self.base_dir / config_file
                    if config_path.exists():
                        tar.add(config_path, arcname=config_file)
                        metadata["files"].append({
                            "path": config_file,
                            "size": config_path.stat().st_size,
                        })

                # Add logs if requested
                if include_logs:
                    logs_dir = self.base_dir / "logs"
                    if logs_dir.exists():
                        for log_file in logs_dir.glob("*.log"):
                            arcname = str(log_file.relative_to(self.base_dir))
                            tar.add(log_file, arcname=arcname)
                            metadata["files"].append({
                                "path": arcname,
                                "size": log_file.stat().st_size,
                            })

            # Get compressed size
            metadata["compressed_size"] = backup_path.stat().st_size
            metadata["compression_ratio"] = (
                metadata["compressed_size"] / metadata["total_size"]
                if metadata["total_size"] > 0 else 1.0
            )

            # Write metadata file
            metadata_path = backup_path.with_suffix(".json")
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)

            print(f"Backup created: {backup_path}")
            print(f"  Files: {len(metadata['files'])}")
            print(f"  Original size: {metadata['total_size'] / 1024 / 1024:.2f} MB")
            print(f"  Compressed size: {metadata['compressed_size'] / 1024 / 1024:.2f} MB")
            print(f"  Compression ratio: {metadata['compression_ratio']:.2%}")

            return backup_path, metadata

        except Exception as e:
            print(f"Backup failed: {e}")
            # Clean up partial backup
            if backup_path.exists():
                backup_path.unlink()
            return None, metadata

    def list_backups(self) -> List[dict]:
        """
        List all existing backups.

        Returns:
            List of backup metadata dictionaries
        """
        backups = []

        for backup_file in sorted(self.backup_dir.glob(f"{self.BACKUP_PREFIX}*{self.BACKUP_EXTENSION}")):
            metadata_file = backup_file.with_suffix(".json")

            backup_info = {
                "filename": backup_file.name,
                "path": str(backup_file),
                "size": backup_file.stat().st_size,
                "created": datetime.fromtimestamp(backup_file.stat().st_mtime),
            }

            # Load metadata if available
            if metadata_file.exists():
                try:
                    with open(metadata_file) as f:
                        backup_info["metadata"] = json.load(f)
                except Exception:
                    pass

            backups.append(backup_info)

        return backups

    def cleanup_old_backups(self) -> List[Path]:
        """
        Remove backups older than retention period.

        Returns:
            List of deleted backup paths
        """
        cutoff = datetime.now() - timedelta(days=self.retention_days)
        deleted = []

        for backup_file in self.backup_dir.glob(f"{self.BACKUP_PREFIX}*{self.BACKUP_EXTENSION}"):
            file_time = datetime.fromtimestamp(backup_file.stat().st_mtime)

            if file_time < cutoff:
                # Delete backup file
                backup_file.unlink()
                deleted.append(backup_file)
                print(f"Deleted old backup: {backup_file.name}")

                # Delete metadata file if exists
                metadata_file = backup_file.with_suffix(".json")
                if metadata_file.exists():
                    metadata_file.unlink()

        if deleted:
            print(f"Cleaned up {len(deleted)} old backup(s)")
        else:
            print("No old backups to clean up")

        return deleted

    def restore_backup(self, backup_path: Path, target_dir: Optional[Path] = None) -> bool:
        """
        Restore from a backup archive.

        Args:
            backup_path: Path to backup archive
            target_dir: Target directory (default: base_dir)

        Returns:
            True if restore successful
        """
        if not backup_path.exists():
            print(f"Backup file not found: {backup_path}")
            return False

        target = Path(target_dir) if target_dir else self.base_dir

        try:
            with tarfile.open(backup_path, "r:gz") as tar:
                # Safety check: ensure no absolute paths or path traversal
                for member in tar.getmembers():
                    if member.name.startswith("/") or ".." in member.name:
                        print(f"Unsafe path in archive: {member.name}")
                        return False

                tar.extractall(target)

            print(f"Restored backup to: {target}")
            return True

        except Exception as e:
            print(f"Restore failed: {e}")
            return False

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()


def main():
    """Main entry point for backup script."""
    parser = argparse.ArgumentParser(
        description="IVT Kinetics Analyzer Backup Tool"
    )
    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove backups older than retention period after creating backup"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List existing backups"
    )
    parser.add_argument(
        "--restore",
        type=str,
        metavar="FILE",
        help="Restore from specified backup file"
    )
    parser.add_argument(
        "--retention",
        type=int,
        default=30,
        help="Backup retention period in days (default: 30)"
    )
    parser.add_argument(
        "--include-logs",
        action="store_true",
        help="Include log files in backup"
    )
    parser.add_argument(
        "--backup-dir",
        type=str,
        help="Custom backup directory"
    )

    args = parser.parse_args()

    # Determine base directory
    base_dir = Path(__file__).parent.parent

    # Initialize backup manager
    backup_dir = Path(args.backup_dir) if args.backup_dir else None
    manager = BackupManager(
        base_dir=base_dir,
        backup_dir=backup_dir,
        retention_days=args.retention,
    )

    if args.list:
        # List backups
        backups = manager.list_backups()
        if backups:
            print(f"\nExisting backups ({len(backups)}):\n")
            for b in backups:
                size_mb = b["size"] / 1024 / 1024
                print(f"  {b['filename']}")
                print(f"    Size: {size_mb:.2f} MB")
                print(f"    Created: {b['created'].strftime('%Y-%m-%d %H:%M:%S')}")
                print()
        else:
            print("No backups found")

    elif args.restore:
        # Restore from backup
        backup_path = Path(args.restore)
        if not backup_path.is_absolute():
            backup_path = manager.backup_dir / backup_path

        print(f"\nRestoring from: {backup_path}")
        print("WARNING: This will overwrite existing files!")
        response = input("Continue? (yes/no): ")

        if response.lower() == "yes":
            if manager.restore_backup(backup_path):
                print("Restore completed successfully")
            else:
                print("Restore failed")
                sys.exit(1)
        else:
            print("Restore cancelled")

    else:
        # Create backup
        print(f"\nCreating backup...")
        backup_path, metadata = manager.create_backup(include_logs=args.include_logs)

        if backup_path:
            print(f"\nBackup saved to: {backup_path}")

            if args.cleanup:
                print(f"\nCleaning up backups older than {args.retention} days...")
                manager.cleanup_old_backups()
        else:
            print("Backup creation failed")
            sys.exit(1)


if __name__ == "__main__":
    main()

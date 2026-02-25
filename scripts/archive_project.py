#!/usr/bin/env python3
"""
Project archival script for IVT Kinetics Analyzer.

Phase 11.7-11.8: Project Archival System (F11.7-F11.8)

Features:
- Compress completed projects to cold storage
- Preserve all data integrity with checksums
- Support restore from archive
- Track archival status in database

Usage:
    python scripts/archive_project.py archive <project_id>   # Archive a project
    python scripts/archive_project.py restore <project_id>   # Restore a project
    python scripts/archive_project.py list                   # List archived projects
    python scripts/archive_project.py status <project_id>    # Check archive status
"""
import os
import sys
import argparse
import tarfile
import shutil
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class ProjectArchiver:
    """Manages project archival to cold storage."""

    ARCHIVE_EXTENSION = ".tar.gz"

    def __init__(
        self,
        base_dir: Path,
        archive_dir: Optional[Path] = None,
    ):
        """
        Initialize project archiver.

        Args:
            base_dir: Application base directory
            archive_dir: Directory for archives (default: base_dir/archives)
        """
        self.base_dir = Path(base_dir)
        self.archive_dir = Path(archive_dir) if archive_dir else self.base_dir / "archives"
        self.data_dir = self.base_dir / "data"

        # Ensure archive directory exists
        self.archive_dir.mkdir(parents=True, exist_ok=True)

    def get_project_data_dir(self, project_id: int) -> Path:
        """Get the data directory for a project."""
        return self.data_dir / str(project_id)

    def archive_project(
        self,
        project_id: int,
        project_name: str,
        username: str,
    ) -> Dict[str, Any]:
        """
        Archive a project to cold storage.

        Args:
            project_id: Project ID
            project_name: Project name for archive filename
            username: User performing the archive

        Returns:
            Archive metadata dictionary
        """
        project_dir = self.get_project_data_dir(project_id)

        if not project_dir.exists():
            return {
                "success": False,
                "error": f"Project data directory not found: {project_dir}",
            }

        # Generate archive filename
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in project_name)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"{safe_name}_{project_id}_{timestamp}{self.ARCHIVE_EXTENSION}"
        archive_path = self.archive_dir / archive_name

        metadata = {
            "project_id": project_id,
            "project_name": project_name,
            "archived_at": datetime.now().isoformat(),
            "archived_by": username,
            "archive_path": str(archive_path),
            "files": [],
            "original_size": 0,
            "compressed_size": 0,
        }

        try:
            # Calculate original size and collect file hashes
            for file_path in project_dir.rglob("*"):
                if file_path.is_file():
                    file_size = file_path.stat().st_size
                    metadata["original_size"] += file_size
                    metadata["files"].append({
                        "path": str(file_path.relative_to(project_dir)),
                        "size": file_size,
                        "sha256": self._compute_file_hash(file_path),
                    })

            # Create archive
            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(project_dir, arcname=str(project_id))

            metadata["compressed_size"] = archive_path.stat().st_size
            metadata["compression_ratio"] = (
                metadata["compressed_size"] / metadata["original_size"]
                if metadata["original_size"] > 0 else 1.0
            )

            # Write metadata file
            metadata_path = archive_path.with_suffix(".json")
            with open(metadata_path, "w") as f:
                json.dump(metadata, f, indent=2)

            # Remove original data directory
            shutil.rmtree(project_dir)

            metadata["success"] = True
            print(f"Project archived successfully: {archive_path}")
            print(f"  Original size: {metadata['original_size'] / 1024 / 1024:.2f} MB")
            print(f"  Compressed size: {metadata['compressed_size'] / 1024 / 1024:.2f} MB")
            print(f"  Files: {len(metadata['files'])}")

            return metadata

        except Exception as e:
            metadata["success"] = False
            metadata["error"] = str(e)
            print(f"Archive failed: {e}")

            # Clean up partial archive
            if archive_path.exists():
                archive_path.unlink()

            return metadata

    def restore_project(
        self,
        project_id: int,
        username: str,
    ) -> Dict[str, Any]:
        """
        Restore a project from archive.

        Args:
            project_id: Project ID to restore
            username: User performing the restore

        Returns:
            Restore result dictionary
        """
        # Find archive file
        archive_path = None
        for archive_file in self.archive_dir.glob(f"*_{project_id}_*{self.ARCHIVE_EXTENSION}"):
            archive_path = archive_file
            break

        if not archive_path:
            return {
                "success": False,
                "error": f"No archive found for project {project_id}",
            }

        # Load metadata
        metadata_path = archive_path.with_suffix(".json")
        if metadata_path.exists():
            with open(metadata_path) as f:
                archive_metadata = json.load(f)
        else:
            archive_metadata = {}

        result = {
            "project_id": project_id,
            "archive_path": str(archive_path),
            "restored_at": datetime.now().isoformat(),
            "restored_by": username,
        }

        try:
            # Extract archive
            with tarfile.open(archive_path, "r:gz") as tar:
                # Safety check
                for member in tar.getmembers():
                    if member.name.startswith("/") or ".." in member.name:
                        result["success"] = False
                        result["error"] = f"Unsafe path in archive: {member.name}"
                        return result

                tar.extractall(self.data_dir)

            # Verify files if metadata available
            if archive_metadata.get("files"):
                project_dir = self.get_project_data_dir(project_id)
                verification_errors = []

                for file_info in archive_metadata["files"]:
                    file_path = project_dir / file_info["path"]
                    if not file_path.exists():
                        verification_errors.append(f"Missing file: {file_info['path']}")
                    elif "sha256" in file_info:
                        actual_hash = self._compute_file_hash(file_path)
                        if actual_hash != file_info["sha256"]:
                            verification_errors.append(f"Hash mismatch: {file_info['path']}")

                if verification_errors:
                    result["verification_errors"] = verification_errors
                    print(f"Warning: {len(verification_errors)} verification errors")

            result["success"] = True
            print(f"Project restored successfully to: {self.get_project_data_dir(project_id)}")

            return result

        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            print(f"Restore failed: {e}")
            return result

    def list_archives(self) -> list:
        """
        List all archived projects.

        Returns:
            List of archive info dictionaries
        """
        archives = []

        for archive_file in sorted(self.archive_dir.glob(f"*{self.ARCHIVE_EXTENSION}")):
            info = {
                "filename": archive_file.name,
                "path": str(archive_file),
                "size": archive_file.stat().st_size,
                "modified": datetime.fromtimestamp(archive_file.stat().st_mtime),
            }

            # Load metadata if available
            metadata_path = archive_file.with_suffix(".json")
            if metadata_path.exists():
                try:
                    with open(metadata_path) as f:
                        info["metadata"] = json.load(f)
                except Exception:
                    pass

            archives.append(info)

        return archives

    def get_archive_status(self, project_id: int) -> Dict[str, Any]:
        """
        Get archive status for a project.

        Args:
            project_id: Project ID

        Returns:
            Status dictionary
        """
        # Check if data directory exists (not archived)
        project_dir = self.get_project_data_dir(project_id)
        if project_dir.exists():
            return {
                "project_id": project_id,
                "is_archived": False,
                "data_dir": str(project_dir),
                "data_size": sum(f.stat().st_size for f in project_dir.rglob("*") if f.is_file()),
            }

        # Check for archive
        for archive_file in self.archive_dir.glob(f"*_{project_id}_*{self.ARCHIVE_EXTENSION}"):
            metadata_path = archive_file.with_suffix(".json")
            metadata = {}
            if metadata_path.exists():
                with open(metadata_path) as f:
                    metadata = json.load(f)

            return {
                "project_id": project_id,
                "is_archived": True,
                "archive_path": str(archive_file),
                "archive_size": archive_file.stat().st_size,
                "archived_at": metadata.get("archived_at"),
                "archived_by": metadata.get("archived_by"),
                "original_size": metadata.get("original_size"),
            }

        return {
            "project_id": project_id,
            "is_archived": False,
            "error": "Project data not found",
        }

    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()


def main():
    """Main entry point for archive script."""
    parser = argparse.ArgumentParser(
        description="IVT Kinetics Analyzer Project Archival Tool"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Archive command
    archive_parser = subparsers.add_parser("archive", help="Archive a project")
    archive_parser.add_argument("project_id", type=int, help="Project ID to archive")
    archive_parser.add_argument("--name", type=str, help="Project name (for filename)")
    archive_parser.add_argument("--user", type=str, default="system", help="Username")

    # Restore command
    restore_parser = subparsers.add_parser("restore", help="Restore a project")
    restore_parser.add_argument("project_id", type=int, help="Project ID to restore")
    restore_parser.add_argument("--user", type=str, default="system", help="Username")

    # List command
    list_parser = subparsers.add_parser("list", help="List archived projects")

    # Status command
    status_parser = subparsers.add_parser("status", help="Check archive status")
    status_parser.add_argument("project_id", type=int, help="Project ID")

    # Common arguments
    parser.add_argument(
        "--archive-dir",
        type=str,
        help="Custom archive directory"
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Determine base directory
    base_dir = Path(__file__).parent.parent

    # Initialize archiver
    archive_dir = Path(args.archive_dir) if args.archive_dir else None
    archiver = ProjectArchiver(base_dir=base_dir, archive_dir=archive_dir)

    if args.command == "archive":
        project_name = args.name or f"project_{args.project_id}"
        result = archiver.archive_project(
            project_id=args.project_id,
            project_name=project_name,
            username=args.user,
        )
        if not result.get("success"):
            print(f"Error: {result.get('error')}")
            sys.exit(1)

    elif args.command == "restore":
        print(f"Restoring project {args.project_id}...")
        result = archiver.restore_project(
            project_id=args.project_id,
            username=args.user,
        )
        if not result.get("success"):
            print(f"Error: {result.get('error')}")
            sys.exit(1)

    elif args.command == "list":
        archives = archiver.list_archives()
        if archives:
            print(f"\nArchived projects ({len(archives)}):\n")
            for a in archives:
                size_mb = a["size"] / 1024 / 1024
                print(f"  {a['filename']}")
                print(f"    Size: {size_mb:.2f} MB")
                print(f"    Modified: {a['modified'].strftime('%Y-%m-%d %H:%M:%S')}")
                if "metadata" in a:
                    meta = a["metadata"]
                    print(f"    Project ID: {meta.get('project_id')}")
                    print(f"    Archived by: {meta.get('archived_by')}")
                print()
        else:
            print("No archived projects found")

    elif args.command == "status":
        status = archiver.get_archive_status(args.project_id)
        print(f"\nProject {args.project_id} status:")
        if status.get("is_archived"):
            print(f"  Status: ARCHIVED")
            print(f"  Archive path: {status.get('archive_path')}")
            print(f"  Archive size: {status.get('archive_size', 0) / 1024 / 1024:.2f} MB")
            print(f"  Archived at: {status.get('archived_at')}")
            print(f"  Archived by: {status.get('archived_by')}")
        elif status.get("error"):
            print(f"  Status: NOT FOUND")
            print(f"  Error: {status.get('error')}")
        else:
            print(f"  Status: ACTIVE")
            print(f"  Data directory: {status.get('data_dir')}")
            print(f"  Data size: {status.get('data_size', 0) / 1024 / 1024:.2f} MB")


if __name__ == "__main__":
    main()

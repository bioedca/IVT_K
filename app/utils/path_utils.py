"""
Path handling utilities for project data storage.

Project names may contain special characters that are unsafe for filesystem paths.
This module provides utilities to generate sanitized slugs for safe storage.
"""
import re
import unicodedata
from pathlib import Path

from app.config import Config


def slugify(name: str) -> str:
    """
    Generate filesystem-safe slug from project name.

    Examples:
        "My Test Project" -> "my_test_project"
        "Tbox Analysis (v2.0)" -> "tbox_analysis_v2_0"
        "Test/Project" -> "test_project"
    """
    # Normalize unicode characters
    name = unicodedata.normalize('NFKD', name)
    name = name.encode('ascii', 'ignore').decode('ascii')
    # Replace special chars (except word chars, spaces, hyphens) with underscores
    name = re.sub(r'[^\w\s-]', '_', name)
    # Collapse multiple underscores/spaces/hyphens into single underscore
    name = re.sub(r'[-_\s]+', '_', name).strip('_')
    return name.lower()


def get_project_data_path(project) -> Path:
    """
    Get filesystem path for project data.

    Args:
        project: Project model instance with name_slug attribute

    Returns:
        Path to project data directory
    """
    return Config.PROJECTS_DIR / project.name_slug


def ensure_project_directories(project) -> dict:
    """
    Ensure all project subdirectories exist.

    Args:
        project: Project model instance

    Returns:
        Dictionary with paths to each subdirectory
    """
    base_path = get_project_data_path(project)

    dirs = {
        "raw": base_path / "raw",
        "processed": base_path / "processed",
        "results": base_path / "results",
        "exports": base_path / "exports",
        "traces": base_path / "traces"
    }

    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)

    return dirs

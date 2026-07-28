"""
Path helpers for portable data mounts and image URLs.

Host paths entered in the UI (e.g. /Users/... or /Volumes/USB/...) are
translated to container paths under /host/... when running in Docker.
Stored image paths are kept relative so a USB knowledge base can move
between machines without rewriting Chroma metadata.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)

# Host roots that docker-compose bind-mounts under /host/<root>
HOST_ROOT_PREFIXES = (
    "/Users",
    "/Volumes",
    "/home",
    "/media",
    "/mnt",
    "/run/media",
)


def running_in_docker() -> bool:
    return Path("/.dockerenv").exists() or os.environ.get("MANUAL_RAG_IN_DOCKER") == "1"


def to_display_path(path: Path | str) -> str:
    """
    Convert a container-visible path back to the host path shown in the UI.
    /host/Users/x → /Users/x
    """
    raw = str(path)
    if raw.startswith("/host/"):
        return "/" + raw[len("/host/") :]
    return raw


def list_browse_roots() -> list[dict]:
    """Return host roots that are currently visible to the process."""
    roots: list[dict] = []
    if running_in_docker():
        for prefix in HOST_ROOT_PREFIXES:
            mirrored = Path("/host") / prefix.lstrip("/")
            if mirrored.is_dir():
                roots.append(
                    {"path": prefix, "label": prefix, "available": True}
                )
        if Path("/app/data").is_dir():
            roots.append(
                {
                    "path": "/app/data",
                    "label": "/app/data (container default)",
                    "available": True,
                }
            )
    else:
        home = Path.home()
        roots.append({"path": str(home), "label": str(home), "available": True})
        for prefix in ("/Volumes", "/media", "/mnt"):
            p = Path(prefix)
            if p.is_dir():
                roots.append({"path": prefix, "label": prefix, "available": True})
        data = Path("./data").resolve()
        if data.is_dir():
            roots.append(
                {"path": str(data), "label": f"{data} (project data)", "available": True}
            )
    return roots


def is_path_allowed(resolved: Path) -> bool:
    """Only allow browsing/mounting under known safe roots."""
    try:
        resolved = resolved.resolve()
    except OSError:
        return False

    allowed: list[Path] = []
    if running_in_docker():
        allowed.append(Path("/app/data"))
        allowed.append(Path("/kb"))
        for prefix in HOST_ROOT_PREFIXES:
            allowed.append(Path("/host") / prefix.lstrip("/"))
    else:
        allowed.append(Path.home())
        allowed.append(Path("./data").resolve())
        for prefix in ("/Volumes", "/media", "/mnt", "/Users", "/home"):
            p = Path(prefix)
            if p.exists():
                allowed.append(p)

    for base in allowed:
        try:
            if not base.exists():
                continue
            resolved.relative_to(base.resolve())
            return True
        except (ValueError, OSError):
            continue
    return False


def list_directory(path_str: str) -> dict:
    """
    List immediate subdirectories for the host browser UI.
    Returns display paths (host-style), not /host/... paths.
    """
    if not path_str or path_str.strip() == "/":
        roots = list_browse_roots()
        return {
            "path": "/",
            "parent": None,
            "entries": [
                {
                    "name": r["label"],
                    "path": r["path"],
                    "is_dir": True,
                    "looks_like_kb": False,
                }
                for r in roots
                if r.get("available")
            ],
            "roots": roots,
            "in_docker": running_in_docker(),
        }

    resolved = resolve_host_path(path_str)
    if not resolved.exists() or not resolved.is_dir():
        raise FileNotFoundError(f"Directory not found: {path_str}")
    if not is_path_allowed(resolved):
        raise PermissionError(f"Browsing is not allowed for: {path_str}")

    display = to_display_path(resolved)
    parent_display: str | None = None
    parent = resolved.parent
    if is_path_allowed(parent) or str(parent) in ("/host", "/"):
        parent_display = to_display_path(parent)
        if parent_display in ("/host", "/"):
            parent_display = "/"

    entries: list[dict] = []
    try:
        children = sorted(resolved.iterdir(), key=lambda p: p.name.lower())
    except PermissionError as e:
        raise PermissionError(f"Cannot read directory: {path_str}") from e

    for child in children:
        name = child.name
        if name.startswith("."):
            continue
        try:
            if not child.is_dir():
                continue
        except OSError:
            continue
        looks_like_kb = (child / "chroma_db").is_dir() or (child / "manuals").is_dir()
        entries.append(
            {
                "name": name,
                "path": to_display_path(child),
                "is_dir": True,
                "looks_like_kb": looks_like_kb,
            }
        )

    return {
        "path": display,
        "parent": parent_display,
        "entries": entries,
        "roots": list_browse_roots(),
        "in_docker": running_in_docker(),
    }


def resolve_host_path(path_str: str) -> Path:
    """
    Resolve a user-supplied path to a filesystem path visible inside the process.

    In Docker:
      /Users/x/data  → /host/Users/x/data   (if that bind exists)
      /Volumes/USB/d → /host/Volumes/USB/d
      /app/data      → /app/data
      /host/Users/x  → /host/Users/x
    Outside Docker: path is used as-is (expanded/resolved).
    """
    raw = path_str.strip()
    if not raw:
        raise ValueError("Path cannot be empty")

    path = Path(raw).expanduser()

    if not running_in_docker():
        return path if path.is_absolute() else Path.cwd() / path

    # Already a container path under /host or /app or /kb
    if raw.startswith(("/host/", "/app/", "/kb/")):
        return Path(raw)

    # Translate common host absolute paths via /host mirror mounts
    for prefix in HOST_ROOT_PREFIXES:
        if raw == prefix or raw.startswith(prefix + "/"):
            translated = Path("/host") / raw.lstrip("/")
            if translated.exists() or translated.parent.exists():
                logger.info("Host path translated: %s → %s", raw, translated)
                return translated
            raise FileNotFoundError(
                f"Host path '{raw}' maps to '{translated}' inside the container, "
                "but it is not available. Ensure docker-compose bind-mounts that "
                "host root (e.g. /Volumes → /host/Volumes) and the folder exists."
            )

    # Container-native path that already exists
    if path.exists():
        return path

    raise FileNotFoundError(
        f"Path '{raw}' is not visible inside the container. "
        "Use a path under /Users, /Volumes, /home, /media, /mnt "
        "(auto-mapped to /host/...), or a bind-mounted path like /app/data or /kb/..."
    )


def to_relative_image_path(path: str | Path, manual_id: str | None = None) -> str:
    """
    Store image paths relative to image_store_dir when possible.
    Falls back to '<manual_id>/<filename>' or the original basename path.
    """
    p = Path(path)
    try:
        return p.resolve().relative_to(settings.image_store_dir.resolve()).as_posix()
    except (ValueError, OSError):
        pass

    if manual_id:
        return f"{manual_id}/{p.name}"
    return p.name


def resolve_stored_image_path(stored: str | None) -> Path | None:
    """Resolve a stored (relative or absolute) image path to a readable file."""
    if not stored:
        return None

    raw = stored.strip()
    candidates: list[Path] = []

    p = Path(raw)
    if p.is_absolute():
        candidates.append(p)
        # Legacy absolute paths from another machine — try basename under image_store_dir
        parts = p.parts
        if "images" in parts:
            idx = parts.index("images")
            rel = Path(*parts[idx + 1 :])
            candidates.append(settings.image_store_dir / rel)
    else:
        candidates.append(settings.image_store_dir / raw)
        candidates.append(Path(raw))

    for candidate in candidates:
        try:
            if candidate.exists() and candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def to_web_image_path(stored: str | None) -> str | None:
    """Convert a stored image path to the /data/images/... URL path."""
    resolved = resolve_stored_image_path(stored)
    if resolved is not None:
        try:
            rel = resolved.resolve().relative_to(settings.image_store_dir.resolve())
            return f"/data/images/{rel.as_posix()}"
        except (ValueError, OSError):
            pass

    if not stored:
        return None
    raw = stored.strip().replace("\\", "/")
    if raw.startswith("/data/images/"):
        return raw
    if raw.startswith("data/images/"):
        return f"/{raw}"
    # Best-effort: treat as relative to image store
    return f"/data/images/{raw.lstrip('/')}"

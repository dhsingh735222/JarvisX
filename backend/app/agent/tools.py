"""Tool registry and implementations for the JarvisX agent.

Every tool is a plain Python function operating on a `ToolContext`. Tools are
described with a JSON-schema `parameters` block so they can be passed to any
LLM provider's "tool use" / "function calling" API in a normalized form.

File-system tools are sandboxed to `settings.WORKSPACE_ROOT` to prevent the
agent from reading or modifying arbitrary paths on the host.
"""

from __future__ import annotations

import datetime
import platform
import shutil
import subprocess
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import MemoryItem

settings = get_settings()


@dataclass
class ToolContext:
    db: Session
    user_id: int


class ToolError(Exception):
    pass


def _workspace_root() -> Path:
    return Path(settings.WORKSPACE_ROOT).expanduser().resolve()


def resolve_path(path: str) -> Path:
    """Resolve a user/agent supplied path against the workspace root and make
    sure it cannot escape it (blocks `..` traversal and absolute paths
    outside the sandbox)."""
    root = _workspace_root()
    candidate = Path(path).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ToolError(
            f"Path '{path}' is outside the allowed workspace ({root}). "
            "Refusing for safety."
        ) from exc
    return resolved


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def tool_get_datetime(ctx: ToolContext, **kwargs: Any) -> dict:
    now = datetime.datetime.now()
    return {
        "iso": now.isoformat(),
        "human_readable": now.strftime("%A, %d %B %Y %H:%M:%S"),
        "timezone": str(datetime.datetime.now().astimezone().tzinfo),
    }


def tool_list_directory(ctx: ToolContext, path: str = ".", **kwargs: Any) -> dict:
    target = resolve_path(path)
    if not target.exists():
        raise ToolError(f"Path does not exist: {target}")
    if not target.is_dir():
        raise ToolError(f"Path is not a directory: {target}")

    entries = []
    for entry in sorted(target.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        try:
            stat = entry.stat()
            entries.append(
                {
                    "name": entry.name,
                    "type": "directory" if entry.is_dir() else "file",
                    "size_bytes": stat.st_size if entry.is_file() else None,
                    "modified": datetime.datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            )
        except OSError:
            continue
    return {"path": str(target), "entries": entries}


def tool_read_text_file(ctx: ToolContext, path: str, max_chars: int = 8000, **kwargs: Any) -> dict:
    target = resolve_path(path)
    if not target.exists() or not target.is_file():
        raise ToolError(f"File does not exist: {target}")
    try:
        content = target.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:  # noqa: BLE001
        raise ToolError(f"Could not read file as text: {exc}") from exc
    truncated = len(content) > max_chars
    return {
        "path": str(target),
        "content": content[:max_chars],
        "truncated": truncated,
        "total_chars": len(content),
    }


def tool_create_directory(ctx: ToolContext, path: str, **kwargs: Any) -> dict:
    target = resolve_path(path)
    if target.exists():
        raise ToolError(f"Path already exists: {target}")
    target.mkdir(parents=True, exist_ok=False)
    return {"created": str(target)}


def tool_create_file(ctx: ToolContext, path: str, content: str = "", overwrite: bool = False, **kwargs: Any) -> dict:
    target = resolve_path(path)
    if target.exists() and not overwrite:
        raise ToolError(
            f"File already exists: {target}. Pass overwrite=true to replace it (requires approval)."
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return {"created": str(target), "bytes_written": len(content.encode("utf-8"))}


def tool_rename_path(ctx: ToolContext, path: str, new_name: str, **kwargs: Any) -> dict:
    target = resolve_path(path)
    if not target.exists():
        raise ToolError(f"Path does not exist: {target}")
    if "/" in new_name or "\\" in new_name:
        raise ToolError("new_name must be a plain file/directory name, not a path")
    destination = target.parent / new_name
    if destination.exists():
        raise ToolError(f"Destination already exists: {destination}")
    target.rename(destination)
    return {"old_path": str(target), "new_path": str(destination)}


def tool_move_path(ctx: ToolContext, source: str, destination: str, **kwargs: Any) -> dict:
    src = resolve_path(source)
    dest = resolve_path(destination)
    if not src.exists():
        raise ToolError(f"Source does not exist: {src}")
    if dest.exists() and dest.is_dir():
        dest = dest / src.name
    shutil.move(str(src), str(dest))
    return {"source": str(src), "destination": str(dest)}


def tool_delete_path(ctx: ToolContext, path: str, **kwargs: Any) -> dict:
    target = resolve_path(path)
    if not target.exists():
        raise ToolError(f"Path does not exist: {target}")
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()
    return {"deleted": str(target)}


def tool_open_application(ctx: ToolContext, name: str, **kwargs: Any) -> dict:
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.Popen(["open", "-a", name])
        elif system == "Windows":
            subprocess.Popen(["cmd", "/c", "start", "", name], shell=False)
        else:  # Linux and others
            subprocess.Popen([name.lower()])
    except FileNotFoundError as exc:
        raise ToolError(f"Could not find application '{name}': {exc}") from exc
    except Exception as exc:  # noqa: BLE001
        raise ToolError(f"Failed to open application '{name}': {exc}") from exc
    return {"opened": name}


def tool_open_url(ctx: ToolContext, url: str, **kwargs: Any) -> dict:
    if not (url.startswith("http://") or url.startswith("https://")):
        url = "https://" + url
    opened = webbrowser.open(url)
    if not opened:
        raise ToolError(f"Could not open browser for URL: {url}")
    return {"opened": url}


def tool_web_search(ctx: ToolContext, query: str, max_results: int = 5, **kwargs: Any) -> dict:
    try:
        from ddgs import DDGS
    except ImportError:
        from duckduckgo_search import DDGS  # type: ignore

    try:
        max_results = int(max_results)
    except (TypeError, ValueError):
        max_results = 5

    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append(
                    {
                        "title": r.get("title"),
                        "url": r.get("href") or r.get("url"),
                        "snippet": r.get("body"),
                    }
                )
    except Exception as exc:  # noqa: BLE001
        raise ToolError(f"Web search failed: {exc}") from exc
    return {"query": query, "results": results}


def tool_remember(ctx: ToolContext, key: str, value: str, category: str = "fact", **kwargs: Any) -> dict:
    existing = (
        ctx.db.query(MemoryItem)
        .filter(MemoryItem.user_id == ctx.user_id, MemoryItem.key == key, MemoryItem.category == category)
        .first()
    )
    if existing:
        existing.value = value
    else:
        existing = MemoryItem(user_id=ctx.user_id, category=category, key=key, value=value)
        ctx.db.add(existing)
    ctx.db.commit()
    return {"remembered": {"category": category, "key": key, "value": value}}


def tool_recall(ctx: ToolContext, query: str = "", category: str | None = None, **kwargs: Any) -> dict:
    q = ctx.db.query(MemoryItem).filter(MemoryItem.user_id == ctx.user_id)
    if category:
        q = q.filter(MemoryItem.category == category)
    items = q.all()
    if query:
        query_lower = query.lower()
        items = [m for m in items if query_lower in m.key.lower() or query_lower in m.value.lower()]
    return {
        "items": [
            {"category": m.category, "key": m.key, "value": m.value, "updated_at": m.updated_at.isoformat()}
            for m in items
        ]
    }


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

@dataclass
class Tool:
    name: str
    description: str
    parameters: dict
    handler: Callable[..., dict]
    requires_approval: bool = False


TOOLS: list[Tool] = [
    Tool(
        name="get_current_datetime",
        description="Get the current date, time and timezone on the user's machine.",
        parameters={"type": "object", "properties": {}, "required": []},
        handler=tool_get_datetime,
    ),
    Tool(
        name="list_directory",
        description="List files and folders inside a directory within the user's workspace.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path relative to the workspace root, or absolute path inside it. Defaults to the workspace root.",
                }
            },
            "required": [],
        },
        handler=tool_list_directory,
    ),
    Tool(
        name="read_text_file",
        description="Read the text content of a file (txt, md, csv, code, etc).",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path to the file to read."},
                "max_chars": {"type": "integer", "description": "Maximum number of characters to return."},
            },
            "required": ["path"],
        },
        handler=tool_read_text_file,
    ),
    Tool(
        name="create_directory",
        description="Create a new directory (and any missing parent directories) inside the workspace.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path of the directory to create."}},
            "required": ["path"],
        },
        handler=tool_create_directory,
    ),
    Tool(
        name="create_file",
        description="Create a new text file with the given content inside the workspace. Fails if the file already exists unless overwrite=true (overwriting requires approval).",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Path of the file to create."},
                "content": {"type": "string", "description": "Text content to write to the file."},
                "overwrite": {"type": "boolean", "description": "Whether to overwrite an existing file."},
            },
            "required": ["path"],
        },
        handler=tool_create_file,
    ),
    Tool(
        name="rename_path",
        description="Rename a file or folder within the workspace. Requires user approval.",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Existing path of the file or folder."},
                "new_name": {"type": "string", "description": "New name (not a full path) for the file or folder."},
            },
            "required": ["path", "new_name"],
        },
        handler=tool_rename_path,
        requires_approval=True,
    ),
    Tool(
        name="move_path",
        description="Move a file or folder to a new location within the workspace. Requires user approval.",
        parameters={
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Path of the file or folder to move."},
                "destination": {"type": "string", "description": "Destination path or directory."},
            },
            "required": ["source", "destination"],
        },
        handler=tool_move_path,
        requires_approval=True,
    ),
    Tool(
        name="delete_path",
        description="Permanently delete a file or folder within the workspace. Requires user approval.",
        parameters={
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Path of the file or folder to delete."}},
            "required": ["path"],
        },
        handler=tool_delete_path,
        requires_approval=True,
    ),
    Tool(
        name="open_application",
        description="Open/launch a desktop application by name (e.g. 'Safari', 'Notepad', 'Visual Studio Code').",
        parameters={
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Name of the application to open."}},
            "required": ["name"],
        },
        handler=tool_open_application,
    ),
    Tool(
        name="open_url",
        description="Open a URL or website in the user's default web browser.",
        parameters={
            "type": "object",
            "properties": {"url": {"type": "string", "description": "URL to open."}},
            "required": ["url"],
        },
        handler=tool_open_url,
    ),
    Tool(
        name="web_search",
        description="Search the web for up-to-date information and return titles, URLs and snippets.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query."},
                "max_results": {"type": "integer", "description": "Maximum number of results to return (default 5)."},
            },
            "required": ["query"],
        },
        handler=tool_web_search,
    ),
    Tool(
        name="remember",
        description="Save a fact, preference or piece of information to long-term memory for future conversations.",
        parameters={
            "type": "object",
            "properties": {
                "key": {"type": "string", "description": "Short label for the memory, e.g. 'favorite_editor'."},
                "value": {"type": "string", "description": "The information to remember."},
                "category": {
                    "type": "string",
                    "description": "One of 'preference', 'fact', or 'task'. Defaults to 'fact'.",
                },
            },
            "required": ["key", "value"],
        },
        handler=tool_remember,
    ),
    Tool(
        name="recall",
        description="Search long-term memory for previously saved facts, preferences or tasks.",
        parameters={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Text to search for within memory keys/values."},
                "category": {"type": "string", "description": "Optionally filter by category."},
            },
            "required": [],
        },
        handler=tool_recall,
    ),
]

TOOLS_BY_NAME: dict[str, Tool] = {t.name: t for t in TOOLS}


def get_tool(name: str) -> Tool:
    tool = TOOLS_BY_NAME.get(name)
    if not tool:
        raise ToolError(f"Unknown tool: {name}")
    return tool


def execute_tool(name: str, tool_input: dict, ctx: ToolContext) -> dict:
    tool = get_tool(name)
    return tool.handler(ctx, **tool_input)

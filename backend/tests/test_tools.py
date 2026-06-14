import pytest

from app.agent import tools as tools_module
from app.agent.tools import ToolContext, ToolError, execute_tool


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(tools_module.settings, "WORKSPACE_ROOT", str(tmp_path))
    return tmp_path


def test_create_and_list_directory(workspace, db_session, test_user):
    ctx = ToolContext(db=db_session, user_id=test_user.id)
    execute_tool("create_directory", {"path": "projects"}, ctx)
    assert (workspace / "projects").is_dir()

    listing = execute_tool("list_directory", {"path": "."}, ctx)
    names = [e["name"] for e in listing["entries"]]
    assert "projects" in names


def test_create_file_and_read(workspace, db_session, test_user):
    ctx = ToolContext(db=db_session, user_id=test_user.id)
    execute_tool("create_file", {"path": "notes/todo.txt", "content": "buy milk"}, ctx)
    result = execute_tool("read_text_file", {"path": "notes/todo.txt"}, ctx)
    assert result["content"] == "buy milk"


def test_create_file_refuses_overwrite(workspace, db_session, test_user):
    ctx = ToolContext(db=db_session, user_id=test_user.id)
    execute_tool("create_file", {"path": "a.txt", "content": "v1"}, ctx)
    with pytest.raises(ToolError):
        execute_tool("create_file", {"path": "a.txt", "content": "v2"}, ctx)


def test_path_traversal_blocked(workspace, db_session, test_user):
    ctx = ToolContext(db=db_session, user_id=test_user.id)
    with pytest.raises(ToolError):
        execute_tool("read_text_file", {"path": "../outside.txt"}, ctx)

    with pytest.raises(ToolError):
        execute_tool("create_directory", {"path": "/etc/jarvisx-should-not-exist"}, ctx)


def test_rename_move_delete(workspace, db_session, test_user):
    ctx = ToolContext(db=db_session, user_id=test_user.id)
    execute_tool("create_file", {"path": "report.txt", "content": "data"}, ctx)

    execute_tool("rename_path", {"path": "report.txt", "new_name": "report_final.txt"}, ctx)
    assert (workspace / "report_final.txt").exists()
    assert not (workspace / "report.txt").exists()

    execute_tool("create_directory", {"path": "archive"}, ctx)
    execute_tool("move_path", {"source": "report_final.txt", "destination": "archive"}, ctx)
    assert (workspace / "archive" / "report_final.txt").exists()

    execute_tool("delete_path", {"path": "archive"}, ctx)
    assert not (workspace / "archive").exists()


def test_remember_and_recall(db_session, test_user):
    ctx = ToolContext(db=db_session, user_id=test_user.id)
    execute_tool("remember", {"key": "favorite_color", "value": "blue", "category": "preference"}, ctx)
    result = execute_tool("recall", {"query": "favorite"}, ctx)
    assert any(item["key"] == "favorite_color" and item["value"] == "blue" for item in result["items"])


def test_get_current_datetime(db_session, test_user):
    ctx = ToolContext(db=db_session, user_id=test_user.id)
    result = execute_tool("get_current_datetime", {}, ctx)
    assert "iso" in result and "human_readable" in result

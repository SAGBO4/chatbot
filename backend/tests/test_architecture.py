"""The API package must not depend on the bot package: shared code lives in app/, the bot builds on it."""
import ast
import pathlib

APP_DIR = pathlib.Path(__file__).resolve().parent.parent / "app"


def _imported_modules(path):
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            yield from (alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.module


def test_app_never_imports_bot():
    offenders = sorted(
        f"{path.relative_to(APP_DIR.parent)} imports {module}"
        for path in APP_DIR.rglob("*.py")
        for module in _imported_modules(path)
        if module == "bot" or module.startswith("bot.")
    )
    assert offenders == []
    assert list(APP_DIR.rglob("*.py")), "no source found: this test would pass vacuously"

"""가드 hook(.claude/hooks/guard.py)의 결정 규칙. 마이그레이션은 local·dev 자동, product 차단."""

import importlib.util
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from types import ModuleType

GUARD = Path(__file__).resolve().parents[3] / ".claude" / "hooks" / "guard.py"


def _load() -> ModuleType:
    spec = importlib.util.spec_from_file_location("guard", GUARD)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load()


def bash(command: str, profile: str | None = None) -> tuple[str, str] | None:
    result: tuple[str, str] | None = guard.decide(
        "Bash", {"command": command}, active_profile=profile
    )
    return result


def files(tool: str, path: str) -> tuple[str, str] | None:
    result: tuple[str, str] | None = guard.decide(tool, {"file_path": path})
    return result


class TestAlembicPolicy:
    @pytest.mark.parametrize("profile", [None, "local", "dev"])
    def test_upgrade_is_allowed_automatically_outside_product(self, profile: str | None) -> None:
        assert bash("cd backend && uv run alembic upgrade head", profile) is None

    @pytest.mark.parametrize("profile", [None, "local", "dev"])
    def test_other_read_and_create_commands_are_allowed(self, profile: str | None) -> None:
        for command in (
            "alembic revision --autogenerate -m x",
            "alembic current",
            "alembic history",
        ):
            assert bash(command, profile) is None

    def test_upgrade_targeting_product_via_active_profile_is_denied(self) -> None:
        decision = bash("uv run alembic upgrade head", "product")

        assert decision is not None
        assert decision[0] == "deny"

    def test_upgrade_targeting_product_via_inline_variable_is_denied(self) -> None:
        for command in (
            "APP_PROFILE=product uv run alembic upgrade head",
            "APP_PROFILE='product' alembic upgrade head",
            'APP_PROFILE="product" alembic upgrade head',
        ):
            decision = bash(command)
            assert decision is not None
            assert decision[0] == "deny"

    def test_inline_non_product_profile_is_not_confused_with_product(self) -> None:
        assert bash("APP_PROFILE=dev alembic upgrade head") is None
        assert bash("APP_PROFILE=product_like_name alembic upgrade head") is None

    @pytest.mark.parametrize("command", ["alembic downgrade -1", "alembic stamp head"])
    @pytest.mark.parametrize("profile", [None, "local", "dev"])
    def test_downgrade_and_stamp_always_need_confirmation(
        self, command: str, profile: str | None
    ) -> None:
        decision = bash(command, profile)

        assert decision is not None
        assert decision[0] == "ask"

    def test_product_denial_takes_precedence_over_confirmation(self) -> None:
        decision = bash("alembic downgrade -1", "product")

        assert decision is not None
        assert decision[0] == "deny"


class TestOtherGuards:
    @pytest.mark.parametrize("tool", ["Read", "Edit", "Write"])
    def test_env_files_are_denied_for_file_tools(self, tool: str) -> None:
        for path in ("/p/backend/.env", "/p/backend/.env.product", "C:\\p\\backend\\.env.local"):
            decision = files(tool, path)
            assert decision is not None
            assert decision[0] == "deny"

    def test_env_example_is_readable_and_writable(self) -> None:
        assert files("Read", "/p/backend/.env.example") is None
        assert files("Edit", "/p/backend/.env.example") is None

    def test_uv_lock_cannot_be_edited_but_can_be_read(self) -> None:
        decision = files("Edit", "/p/backend/uv.lock")

        assert decision is not None
        assert decision[0] == "deny"
        assert files("Read", "/p/backend/uv.lock") is None

    def test_pip_install_and_venv_are_denied(self) -> None:
        for command in (
            "pip install requests",
            "python -m venv .venv",
            "echo hi && pip3 install x",
        ):
            decision = bash(command)
            assert decision is not None
            assert decision[0] == "deny"

    def test_commands_mentioning_env_files_need_confirmation(self) -> None:
        decision = bash("cat backend/.env")

        assert decision is not None
        assert decision[0] == "ask"

    def test_env_example_and_environ_in_commands_are_not_flagged(self) -> None:
        assert bash("cp backend/.env.example /tmp/x.txt") is None
        assert bash('python -c "import os; print(os.environ)"') is None

    def test_ordinary_commands_pass(self) -> None:
        assert bash("uv run pytest -q") is None
        assert bash("git status") is None

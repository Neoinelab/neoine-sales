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
    def test_downgrade_and_stamp_are_allowed_outside_product(
        self, command: str, profile: str | None
    ) -> None:
        assert bash(command, profile) is None

    def test_downgrade_targeting_product_is_denied(self) -> None:
        decision = bash("alembic downgrade -1", "product")

        assert decision is not None
        assert decision[0] == "deny"


class TestOtherGuards:
    def test_env_files_cannot_be_read_into_the_conversation(self) -> None:
        for path in ("/p/backend/.env", "/p/backend/.env.product", "C:\\p\\backend\\.env.local"):
            decision = files("Read", path)
            assert decision is not None
            assert decision[0] == "deny"

    @pytest.mark.parametrize("tool", ["Edit", "Write"])
    def test_env_files_can_be_edited_without_confirmation(self, tool: str) -> None:
        for path in ("/p/backend/.env", "/p/backend/.env.dev"):
            assert files(tool, path) is None

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

    def test_commands_that_print_env_files_are_denied(self) -> None:
        for command in (
            "cat backend/.env",
            "head -5 .env.dev",
            "cd backend && tail .env",
            "grep APP_DATABASE_URL backend/.env",
            "less .env",
        ):
            decision = bash(command)
            assert decision is not None, command
            assert decision[0] == "deny"

    def test_commands_that_change_env_files_without_printing_pass(self) -> None:
        for command in (
            "cd backend && sed -e 's/a/b/' .env > .env.dev",
            "sed -i '' 's/^APP_PROFILE=.*/APP_PROFILE=dev/' backend/.env.dev",
            "echo 'APP_COOKIE_SECURE=false' >> .env.dev",
            "grep -q '^APP_PROFILE=' .env.dev || echo x >> .env.dev",
            "chmod 600 backend/.env.dev",
            "test -f backend/.env.dev",
        ):
            assert bash(command) is None, command

    def test_searching_text_for_the_word_env_is_not_treated_as_printing(self) -> None:
        for command in (
            'grep -rn "\\.env" CLAUDE.md docs',
            "grep -n '.env 파일' docs/dev-guide.html",
            "cat README.md | grep env",
        ):
            assert bash(command) is None, command

    def test_env_example_and_environ_in_commands_are_not_flagged(self) -> None:
        assert bash("cp backend/.env.example /tmp/x.txt") is None
        assert bash('python -c "import os; print(os.environ)"') is None

    def test_ordinary_commands_pass(self) -> None:
        assert bash("uv run pytest -q") is None
        assert bash("git status") is None


class TestSetupScriptPolicy:
    """setup.sh의 product·서버 모드(sudo, systemd, product 준비)는 Claude가 실행하지 않는다."""

    @pytest.mark.parametrize(
        "command",
        [
            "scripts/setup.sh --profile product",
            "./scripts/setup.sh --profile product --skip-migrate",
            "bash scripts/setup.sh --profile product",
            "cd /repo && ./scripts/setup.sh --profile product",
            "./scripts/setup.sh --server",
            "bash scripts/setup.sh --profile dev --server",
            "sudo ./scripts/setup.sh --profile dev --server --tag v1",
            "APP_PROFILE=dev ./scripts/setup.sh --profile product",
            "/abs/path/scripts/setup.sh --profile dev --server",
            "bash -x scripts/setup.sh --profile product",
            "/bin/bash -x scripts/setup.sh --profile dev --server",
            "bash -e scripts/setup.sh --server",
            "bash -c 'scripts/setup.sh --profile product'",
            "sudo -u me ./scripts/setup.sh --server",
            "env -i ./scripts/setup.sh --server",
            "(cd scripts && ./setup.sh --profile product)",
            "./scripts/setup.sh --profile=product",
            "bash scripts/setup.sh --profile=product",
            "bash -lc 'cd x && ./scripts/setup.sh --server'",
            "bash -xc './scripts/setup.sh --profile product'",
            "zsh -ic './setup.sh --server'",
            "X=$(./scripts/setup.sh --server)",
            "echo $(./scripts/setup.sh --server)",
            "echo `./scripts/setup.sh --server`",
        ],
    )
    def test_product_or_server_mode_is_denied(self, command: str) -> None:
        decision = bash(command)

        assert decision is not None
        assert decision[0] == "deny"

    @pytest.mark.parametrize("profile", [None, "local", "dev", "product"])
    def test_product_or_server_mode_is_denied_regardless_of_active_profile(
        self, profile: str | None
    ) -> None:
        decision = bash("./scripts/setup.sh --profile dev --server", profile)

        assert decision is not None
        assert decision[0] == "deny"

    @pytest.mark.parametrize(
        "command",
        [
            "scripts/setup.sh",
            "./scripts/setup.sh --profile local",
            "./scripts/setup.sh --profile dev",
            "./scripts/setup.sh --profile dev --skip-migrate",
            "bash scripts/setup.sh --help",
            "bash scripts/setup.sh -h",
            "./scripts/setup.sh --profile product --help",
            "git commit -m './scripts/setup.sh --server 추가 && 기타'",
        ],
    )
    def test_local_and_dev_pc_modes_are_allowed(self, command: str) -> None:
        assert bash(command) is None

    @pytest.mark.parametrize(
        "command",
        [
            "bash -n scripts/setup.sh",
            "cat scripts/setup.sh",
            "git add scripts/setup.sh",
            "bash scripts/tests/test_setup.sh",
            "bash infra/server/tests/test_env_secrets.sh",
            "grep -n server scripts/setup.sh",
            "./scripts/start-backend.sh --profile dev",
        ],
    )
    def test_commands_that_only_mention_setup_script_are_allowed(self, command: str) -> None:
        assert bash(command) is None

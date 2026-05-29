#!/usr/bin/env python3
"""Invoke a semantic triage role using Python-only harness wiring."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any


ANSI_COLORS = {
    "red": "31",
    "green": "32",
    "yellow": "33",
    "cyan": "36",
    "darkcyan": "36",
    "magenta": "35",
    "gray": "37",
    "darkgray": "90",
}


def read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def console_colors_enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    term = os.environ.get("TERM", "")
    if term.lower() == "dumb":
        return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def colorize(text: str, color: str | None = None) -> str:
    code = ANSI_COLORS.get(str(color or "").lower())
    if not code or not console_colors_enabled():
        return text
    return f"\x1b[{code}m{text}\x1b[0m"


def append_log_line(console_log: Path, text: str) -> None:
    console_log.parent.mkdir(parents=True, exist_ok=True)
    with open(console_log, "a", encoding="utf-8") as f:
        f.write(text + "\n")


def emit_line(console_log: Path, text: str, color: str | None = None) -> None:
    print(colorize(text, color), flush=True)
    append_log_line(console_log, text)


def render_text_block(console_log: Path, label: str, text: str, label_color: str, text_color: str) -> None:
    emit_line(console_log, f"  {label}", label_color)
    for line in str(text).replace("\r\n", "\n").split("\n"):
        emit_line(console_log, f"    {line}", text_color)


def render_agent_stream_line(role_name: str, stream_name: str, line: str, console_log: Path) -> None:
    """Render one Claude stream-json line with dev-harness-style labels and colors."""
    if not line:
        return
    try:
        event = json.loads(line)
    except json.JSONDecodeError:
        render_text_block(console_log, f"[{stream_name}]", line, "gray", "gray")
        return

    if event.get("type") == "system" and event.get("subtype") == "init":
        emit_line(console_log, f"  [START] role={role_name} model={event.get('model', 'unknown')}", "cyan")
        return

    if event.get("type") == "assistant":
        for part in event.get("message", {}).get("content", []):
            if part.get("type") == "text" and part.get("text"):
                render_text_block(console_log, "[AI]", str(part["text"]), "cyan", "cyan")
            elif part.get("type") == "tool_use":
                emit_line(console_log, f"  [TOOL] {part.get('name', 'tool')}", "yellow")
            elif part.get("type") == "thinking":
                emit_line(console_log, "  [THINKING] hidden internal reasoning; follow AI text and result.", "darkcyan")
        return

    if event.get("type") == "result":
        subtype = event.get("subtype", "result")
        color = "red" if event.get("is_error") else "green"
        emit_line(console_log, f"  [DONE] {subtype}", color)
        if event.get("result"):
            render_text_block(console_log, "[RESULT]", str(event["result"]), color, color)
        return

    if event.get("type") == "user":
        render_text_block(console_log, "[USER EVENT]", line, "magenta", "gray")
        return

    render_text_block(console_log, f"[{stream_name}]", line, "gray", "gray")


def test_env_name(name: str | None) -> bool:
    return bool(name and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name))


def get_provider_family(provider_name: str, provider: dict[str, Any]) -> str:
    if provider.get("family"):
        return str(provider["family"]).lower()
    if re.search(r"claude|anthropic|glm", provider_name or "", re.IGNORECASE):
        return "anthropic"
    return "openai"


def get_default_env_name(kind: str, family: str, is_claude: bool) -> str:
    is_anthropic = family == "anthropic" or is_claude
    if kind == "base":
        return "ANTHROPIC_BASE_URL" if is_anthropic else "OPENAI_BASE_URL"
    if kind == "key":
        return "ANTHROPIC_API_KEY" if is_anthropic else "OPENAI_API_KEY"
    if kind == "auth":
        return "ANTHROPIC_AUTH_TOKEN"
    if kind == "model":
        return "ANTHROPIC_MODEL" if is_anthropic else "OPENAI_MODEL"
    return kind


def resolve_configured_binding(default_env: str, config_value: Any) -> dict[str, str | None]:
    if config_value is None:
        return {"env": default_env, "value": None}
    if isinstance(config_value, str):
        if test_env_name(config_value):
            return {"env": config_value, "value": os.environ.get(config_value)}
        return {"env": default_env, "value": config_value}
    if isinstance(config_value, dict):
        env_name = config_value.get("env") if test_env_name(config_value.get("env")) else default_env
        value = None
        if config_value.get("value"):
            value = str(config_value["value"])
        elif test_env_name(config_value.get("env")):
            value = os.environ.get(str(config_value["env"]))
        return {"env": env_name, "value": value}
    return {"env": default_env, "value": str(config_value)}


def set_provider_environment(config: dict[str, Any], role: dict[str, Any], command: str) -> dict[str, str | None]:
    provider_name = role.get("provider", "")
    provider = config.get("providers", {}).get(provider_name, {})
    if not provider:
        return {}

    family = get_provider_family(provider_name, provider)
    is_claude = command == "claude"
    is_anthropic = family == "anthropic" or is_claude

    base_config = provider.get("base_url")
    key_config = provider.get("api_key")
    auth_config = provider.get("auth_token")
    model_config = provider.get("model")

    provider_env = provider.get("env") or {}
    if not base_config:
        base_config = provider_env.get("OPENAI_BASE_URL") if is_claude else provider_env.get("ANTHROPIC_BASE_URL")
    if not key_config:
        key_config = provider_env.get("OPENAI_API_KEY") if is_claude else provider_env.get("ANTHROPIC_API_KEY")
    if not auth_config:
        auth_config = provider_env.get("ANTHROPIC_AUTH_TOKEN") or (provider_env.get("OPENAI_API_KEY") if is_claude else None)

    bindings = [
        resolve_configured_binding(get_default_env_name("base", family, is_claude), base_config),
        resolve_configured_binding(get_default_env_name("key", family, is_claude), key_config),
        resolve_configured_binding(get_default_env_name("auth", family, is_claude), auth_config),
        resolve_configured_binding(get_default_env_name("model", family, is_claude), model_config),
    ]
    if not bindings[-1].get("value") and provider.get("model_env"):
        bindings[-1] = resolve_configured_binding(
            get_default_env_name("model", family, is_claude),
            provider.get("model_env"),
        )

    conflicts = (
        ["OPENAI_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL"]
        if is_anthropic
        else ["ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_MODEL"]
    )

    old: dict[str, str | None] = {}
    for binding in bindings:
        env_name = binding.get("env")
        value = binding.get("value")
        if env_name and value:
            old.setdefault(env_name, os.environ.get(env_name))
    for name in conflicts:
        old.setdefault(name, os.environ.get(name))

    for name in conflicts:
        os.environ.pop(name, None)
    for binding in bindings:
        env_name = binding.get("env")
        value = binding.get("value")
        if env_name and value:
            os.environ[env_name] = value

    for env_name, env_value in provider_env.items():
        if is_claude and is_anthropic and env_name.startswith("OPENAI_"):
            continue
        if isinstance(env_value, str):
            old.setdefault(env_name, os.environ.get(env_name))
            os.environ[env_name] = env_value

    return old


def restore_environment(old: dict[str, str | None]) -> None:
    for name, value in old.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def get_role_configured_model(config: dict[str, Any], role: dict[str, Any]) -> str:
    provider = config.get("providers", {}).get(role.get("provider", ""), {})
    if provider.get("model"):
        return str(provider["model"])
    if provider.get("model_env"):
        return os.environ.get(str(provider["model_env"]), "")
    return ""


def add_claude_model_arg(cli_args: list[str], model: str) -> list[str]:
    if not model:
        return list(cli_args)
    if any(arg == "--model" or arg.startswith("--model=") for arg in cli_args):
        return list(cli_args)
    return ["--model", model] + list(cli_args)


def set_claude_project_settings(config: dict[str, Any], role: dict[str, Any], model: str) -> dict[str, Any] | None:
    provider_name = role.get("provider", "")
    provider = config.get("providers", {}).get(provider_name, {})
    if not provider:
        return None
    family = get_provider_family(provider_name, provider)
    if family == "openai":
        family = "anthropic"

    repo_root = Path(__file__).resolve().parents[3]
    settings_path = repo_root / ".claude" / "settings.local.json"
    backup = {
        "path": settings_path,
        "existed": settings_path.exists(),
        "content": settings_path.read_text(encoding="utf-8") if settings_path.exists() else None,
    }

    if family == "anthropic":
        env_block = {
            "ANTHROPIC_BASE_URL": os.environ.get("ANTHROPIC_BASE_URL"),
            "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY"),
            "ANTHROPIC_AUTH_TOKEN": os.environ.get("ANTHROPIC_AUTH_TOKEN"),
            "ANTHROPIC_MODEL": os.environ.get("ANTHROPIC_MODEL"),
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": model or os.environ.get("ANTHROPIC_DEFAULT_HAIKU_MODEL"),
            "ANTHROPIC_DEFAULT_SONNET_MODEL": model or os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL"),
            "ANTHROPIC_DEFAULT_OPUS_MODEL": model or os.environ.get("ANTHROPIC_DEFAULT_OPUS_MODEL"),
        }
        settings: dict[str, Any] = {"env": env_block, "model": "opus"}
    else:
        env_block = {
            "OPENAI_BASE_URL": os.environ.get("OPENAI_BASE_URL"),
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "OPENAI_MODEL": os.environ.get("OPENAI_MODEL"),
        }
        settings = {"env": env_block}
    write_json(settings_path, settings)
    return backup


def restore_claude_project_settings(backup: dict[str, Any] | None) -> None:
    if not backup:
        return
    path: Path = backup["path"]
    if backup["existed"]:
        path.write_text(str(backup["content"]), encoding="utf-8")
    elif path.exists():
        path.unlink()


def invoke_role(args: argparse.Namespace) -> int:
    config_path = Path(args.ConfigPath)
    config = read_json(config_path)
    if not config:
        print(f"Cannot read config: {config_path}", file=sys.stderr)
        return 1

    role = config.get("roles", {}).get(args.RoleName)
    if not role:
        print(f"Role '{args.RoleName}' not found", file=sys.stderr)
        return 1

    command = str(role.get("command", "claude"))
    role_args = [str(item) for item in role.get("args", [])]
    model = args.Model or get_role_configured_model(config, role)

    provider = config.get("providers", {}).get(role.get("provider", ""), {})
    provider_family = get_provider_family(role.get("provider", ""), provider)
    if command == "claude" and model and provider_family == "anthropic":
        role_args = add_claude_model_arg(role_args, model)

    prompt_path = Path(args.PromptFile)
    if not prompt_path.exists():
        print(f"Prompt file not found: {prompt_path}", file=sys.stderr)
        return 1
    prompt = prompt_path.read_text(encoding="utf-8")

    output_path = Path(args.OutputFile)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    log_dir = Path(args.LogDir)
    log_dir.mkdir(parents=True, exist_ok=True)
    console_log = log_dir / "console.log"
    stdout_log = log_dir / "stdout.jsonl"
    stderr_log = log_dir / "stderr.log"
    stdout_log.write_text("", encoding="utf-8")
    stderr_log.write_text("", encoding="utf-8")

    env_backup: dict[str, str | None] = {}
    settings_backup = None
    try:
        env_backup = set_provider_environment(config, role, command)
        if command == "claude":
            settings_backup = set_claude_project_settings(config, role, model)

        command_path = shutil.which(command) or command
        emit_line(console_log, "", "darkcyan")
        emit_line(console_log, "==================================================", "darkcyan")
        emit_line(console_log, f"  AI role: {args.RoleName}", "cyan")
        emit_line(console_log, "==================================================", "darkcyan")
        append_log_line(console_log, "[COMMAND]")
        append_log_line(console_log, f"{command_path} {' '.join(role_args)}")

        proc = subprocess.Popen(
            [command_path] + role_args,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=Path.cwd(),
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )

        if proc.stdin:
            proc.stdin.write((prompt + "\n").encode("utf-8"))
            proc.stdin.close()

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []

        def read_stream(stream, sink: list[str], raw_log: Path, name: str) -> None:
            try:
                for raw_line in stream:
                    line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                    sink.append(line)
                    with open(raw_log, "a", encoding="utf-8") as f:
                        f.write(line + "\n")
                    render_agent_stream_line(args.RoleName, name, line, console_log)
            except Exception as exc:
                append_log_line(console_log, f"[STREAM ERROR] {name}: {exc}")

        stdout_thread = threading.Thread(
            target=read_stream,
            args=(proc.stdout, stdout_lines, stdout_log, "stdout"),
            daemon=True,
        )
        stderr_thread = threading.Thread(
            target=read_stream,
            args=(proc.stderr, stderr_lines, stderr_log, "stderr"),
            daemon=True,
        )
        stdout_thread.start()
        stderr_thread.start()

        timed_out = False
        deadline = time.time() + 180
        while proc.poll() is None:
            if time.time() > deadline:
                timed_out = True
                proc.kill()
                break
            time.sleep(0.05)

        stdout_thread.join(timeout=2)
        stderr_thread.join(timeout=2)

        exit_code = 1 if timed_out else int(proc.returncode or 0)
        if timed_out:
            emit_line(console_log, "  [TIMEOUT] semantic role call exceeded 180s", "red")

        stdout_text = "\n".join(stdout_lines)
        stderr_text = "\n".join(stderr_lines)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(stdout_text, encoding="utf-8")
        write_json(
            log_dir / "semantic-call.json",
            {
                "timestamp": datetime.now().isoformat(),
                "role": args.RoleName,
                "provider": role.get("provider", ""),
                "model": model,
                "exit_code": exit_code,
                "prompt_file": str(prompt_path),
                "output_file": str(output_path),
                "console_log": str(console_log),
                "stdout_log": str(stdout_log),
                "stderr_log": str(stderr_log),
                "stdout_lines": len(stdout_lines),
                "stderr_lines": len(stderr_lines),
            },
        )
        if exit_code != 0:
            print(f"Role invocation failed with exit code {exit_code}", file=sys.stderr)
            if stderr_text:
                print(stderr_text[:500], file=sys.stderr)
            return exit_code
        print(f"Semantic role call completed. Exit code: {exit_code}")
        print(f"Output: {output_path}")
        return 0
    finally:
        restore_claude_project_settings(settings_backup)
        restore_environment(env_backup)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ConfigPath", required=True)
    parser.add_argument("--RoleName", required=True)
    parser.add_argument("--PromptFile", required=True)
    parser.add_argument("--OutputFile", required=True)
    parser.add_argument("--LogDir", required=True)
    parser.add_argument("--Model", default="")
    return invoke_role(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())

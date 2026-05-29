#!/usr/bin/env python3
"""auto_harness_loop.py - Python parity of auto_harness_loop.py"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from harness_shared import (
    ensure_dir,
    read_json,
    write_json,
    utc_now_iso,
    today_iso,
    now_iso,
    filter_local_workspace_paths,
    is_local_workspace_path,
    get_field_value,
    normalize_inline_value,
)

# ---------------------------------------------------------------------------
# Global state (mirrors Python module-level variables)
# ---------------------------------------------------------------------------
WorkerId = ""
RepoRoot = ""
AutomationRoot = ""
LogRoot = ""
RunStamp = ""
RunLogDir = ""
RunConsoleLog = ""
LatestFile = ""
DryRun = False
StatePath = ""
ProgramStatePath = ""

LatestRoundName = ""
LatestRoleName = ""
LatestCallName = ""
LatestCallDir = ""
AgentDisplayEmitHost = True
AgentDisplayBuffer = None
AgentStepCounts = {}
ResumeTaskBriefPath = None
LastRunSummary = None
LastRoundSummary = None
LastTraceSummary = None

ANSI_COLORS = {
    "black": "30",
    "red": "31",
    "green": "32",
    "yellow": "33",
    "blue": "34",
    "magenta": "35",
    "cyan": "36",
    "gray": "37",
    "darkgray": "90",
    "darkred": "91",
    "darkgreen": "92",
    "darkyellow": "93",
    "darkblue": "94",
    "darkmagenta": "95",
    "darkcyan": "96",
    "white": "97",
}


# ---------------------------------------------------------------------------
# Set-ClaudeProjectSettings: override project Claude settings per role
# Get-ProviderFamily: distinguish OpenAI and Anthropic providers
# ---------------------------------------------------------------------------

def console_colors_enabled():
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    term = os.environ.get("TERM", "")
    if term.lower() == "dumb":
        return False
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def colorize(text, color=None):
    if not color or not console_colors_enabled():
        return text
    code = ANSI_COLORS.get(str(color).lower())
    if not code:
        return text
    return f"\x1b[{code}m{text}\x1b[0m"


def print_host(text="", color=None):
    print(colorize(text, color), flush=True)


def runlog_color(level):
    return {
        "ERROR": "red",
        "WARN": "yellow",
        "INFO": "gray",
        "PASS": "green",
        "DONE": "green",
        "FAILED": "red",
    }.get(str(level).upper(), "gray")


def write_runlog(level, message):
    global RunConsoleLog, WorkerId
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [{WorkerId}] [{level}] {message}"
    print_host(line, runlog_color(level))
    try:
        with open(RunConsoleLog, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def convert_to_safe_name(value):
    if not value:
        return "main"
    safe = re.sub(r"[^a-z0-9_-]+", "-", value.lower())
    safe = safe.strip("-")
    if not safe:
        return "main"
    return safe


def set_latest_call_path(path, round_name, role_name, call_name):
    global LatestRoundName, LatestRoleName, LatestCallName, LatestCallDir
    if path:
        try:
            resolved = str(Path(path).resolve())
            with open(LatestFile, "w", encoding="utf-8") as f:
                f.write(resolved)
        except Exception:
            pass
    LatestRoundName = round_name
    LatestRoleName = role_name
    LatestCallName = call_name
    LatestCallDir = str(Path(path).resolve()) if path else None


def new_agent_call_directory(base_dir, role_name, call_kind="main"):
    role_dir = Path(base_dir) / role_name
    ensure_dir(role_dir)
    safe_kind = convert_to_safe_name(call_kind)
    return {"role_dir": str(role_dir.resolve()), "phase": safe_kind}


def convert_agent_escaped_text(text):
    if text is None:
        return ""
    return text.replace("\\r\\n", "\r\n").replace("\\n", "\n").replace("\\t", "\t")


def write_agent_display_log_line(role_name, text):
    global AgentDisplayBuffer
    if AgentDisplayBuffer is not None:
        AgentDisplayBuffer.append(text)


def get_agent_display_lines(text, head_lines=20, tail_lines=10):
    expanded = convert_agent_escaped_text(text)
    if not expanded.strip():
        return []
    lines = expanded.split("\n")
    # remove trailing \r from each line
    lines = [l.rstrip("\r") for l in lines]
    if len(lines) > (head_lines + tail_lines):
        result = [f"(lines={len(lines)}, showing first {head_lines} + last {tail_lines})"]
        result.extend(lines[:head_lines])
        result.append(f"... omitted {len(lines) - head_lines - tail_lines} line(s) ...")
        result.extend(lines[-tail_lines:])
        return result
    return lines


def write_agent_console_block(
    role_name,
    label,
    text,
    label_color="cyan",
    text_color="gray",
    head_lines=20,
    tail_lines=10,
):
    global AgentDisplayEmitHost
    lines = get_agent_display_lines(text, head_lines, tail_lines)
    if not lines:
        return
    if AgentDisplayEmitHost:
        print_host(f"  {label}", label_color)
    write_agent_display_log_line(role_name, f"  {label}")
    for entry in lines:
        if AgentDisplayEmitHost:
            print_host(f"    {entry}", text_color)
        write_agent_display_log_line(role_name, f"    {entry}")


def convert_agent_input_json(input_obj):
    if not input_obj:
        return ""
    try:
        text = json.dumps(input_obj, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        text = str(input_obj)
    text = text.replace("\\u0026", "&").replace("\\u003c", "<").replace("\\u003e", ">")
    return text


def write_agent_console_event(role_name, stream_name, line):
    global AgentStepCounts, AgentDisplayEmitHost
    if not line:
        return
    if line.startswith("__AUTO_HARNESS_"):
        if AgentDisplayEmitHost:
            print_host(f"  [{line}]", "darkgray")
        write_agent_display_log_line(role_name, f"  [{line}]")
        return
    try:
        evt = json.loads(line)
    except Exception:
        write_agent_console_block(role_name, f"[{stream_name}]", line, head_lines=20, tail_lines=10)
        return

    if evt.get("type") == "system" and evt.get("subtype") == "init":
        model = evt.get("model", "unknown")
        if AgentDisplayEmitHost:
            print_host(f"  [START] role={role_name} model={model}", "cyan")
        write_agent_display_log_line(role_name, f"  [START] role={role_name} model={model}")
        return

    if evt.get("type") == "assistant" and evt.get("message", {}).get("content"):
        for part in evt["message"]["content"]:
            if part.get("type") == "text" and part.get("text"):
                write_agent_console_block(role_name, "[AI]", str(part["text"]), label_color="cyan", text_color="cyan", head_lines=30, tail_lines=12)
            elif part.get("type") == "tool_use":
                tool_name = part.get("name", "tool")
                if role_name not in AgentStepCounts:
                    AgentStepCounts[role_name] = 0
                AgentStepCounts[role_name] += 1
                step = AgentStepCounts[role_name]
                if AgentDisplayEmitHost:
                    print_host("")
                    print_host(f"  [{step}] {tool_name}", "yellow")
                write_agent_display_log_line(role_name, "")
                write_agent_display_log_line(role_name, f"  [{step}] {tool_name}")
                if part.get("input"):
                    input_json = convert_agent_input_json(part["input"])
                    write_agent_console_block(role_name, "[INPUT]", input_json, label_color="darkyellow", text_color="darkyellow", head_lines=30, tail_lines=10)
            elif part.get("type") == "thinking":
                if AgentDisplayEmitHost:
                    print_host("  [THINKING] hidden internal reasoning; follow AI text, tool calls, and tool output.", "darkcyan")
                write_agent_display_log_line(role_name, "  [THINKING] hidden internal reasoning; follow AI text, tool calls, and tool output.")
        return

    if evt.get("type") == "user" and evt.get("message", {}).get("content"):
        for part in evt["message"]["content"]:
            if part.get("type") == "tool_result":
                label = "[TOOL OUTPUT: ERROR]" if part.get("is_error") else "[TOOL OUTPUT]"
                if part.get("content"):
                    write_agent_console_block(role_name, label, str(part["content"]), label_color="magenta", text_color="darkgray", head_lines=12, tail_lines=8)
                else:
                    if AgentDisplayEmitHost:
                        print_host(f"  {label} <empty>", "magenta")
                    write_agent_display_log_line(role_name, f"  {label} <empty>")
            elif part.get("type") == "text" and part.get("text"):
                write_agent_console_block(role_name, "[用户事件]", str(part["text"]), label_color="darkgray", text_color="darkgray", head_lines=12, tail_lines=6)
        return

    if evt.get("type") == "result":
        subtype = evt.get("subtype", "result")
        if AgentDisplayEmitHost:
            print_host("")
            print_host(f"  [DONE] {subtype}", "green")
        write_agent_display_log_line(role_name, "")
        write_agent_display_log_line(role_name, f"  [DONE] {subtype}")
        if evt.get("result"):
            write_agent_console_block(role_name, "[RESULT]", str(evt["result"]), label_color="green", text_color="darkgreen", head_lines=12, tail_lines=6)
        return

    if evt.get("type"):
        return


def write_agent_stream_line(role_name, stream_name, line):
    if line is None:
        return
    write_agent_console_event(role_name, stream_name, line)


def add_agent_aggregate_console_log(call_text, role_dir, round_dir, role_name, phase, run_dir=None):
    if not call_text:
        return
    global RunLogDir
    if run_dir is None:
        run_dir = RunLogDir
    role_console_path = os.path.join(role_dir, "console.log")
    run_console_path = os.path.join(run_dir, "console.log")
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    block_header = (
        "\r\n"
        "################################################################################\r\n"
        f"role={role_name} phase={phase} at={ts}\r\n"
        "################################################################################"
    )
    ensure_dir(Path(role_dir))
    with open(role_console_path, "a", encoding="utf-8") as f:
        f.write(block_header + "\r\n" + call_text.rstrip() + "\r\n")
    try:
        ensure_dir(Path(run_dir))
        round_leaf = os.path.basename(round_dir)
        with open(run_console_path, "a", encoding="utf-8") as f:
            f.write(block_header + "\r\n" + f"[ROLE LOG] {round_leaf} / {role_name} / {phase} -> {role_console_path}\r\n")
    except Exception:
        pass


def add_command_console_log(command_string, result, round_dir="", label="COMMAND"):
    global RunConsoleLog, RunLogDir
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    output_text = result.get("output", "(no output)") if result.get("output") else "(no output)"
    block = (
        "\r\n"
        "################################################################################\r\n"
        f"{label} at={ts}\r\n"
        "################################################################################\r\n"
        "[COMMAND]\r\n"
        f"{command_string}\r\n"
        "\r\n"
        "[EXIT]\r\n"
        f"ok={result.get('ok', False)} exit_code={result.get('exit_code', 1)}\r\n"
        "\r\n"
        "[OUTPUT]\r\n"
        + str(output_text).rstrip() + "\r\n"
    )
    with open(RunConsoleLog, "a", encoding="utf-8") as f:
        f.write(block)
    if round_dir:
        rd = Path(round_dir)
        try:
            if str(rd.resolve()) != str(Path(RunLogDir).resolve()):
                ensure_dir(rd)
                with open(rd / "console.log", "a", encoding="utf-8") as f:
                    f.write(block)
        except Exception:
            pass


def read_json_file(path):
    p = Path(path)
    if not p.exists():
        return None
    return read_json(p)


def write_json_file(path, value):
    global DryRun, StatePath, ProgramStatePath
    p = Path(path)
    ensure_dir(p.parent)
    if DryRun:
        target_path = str(p.resolve())
        for state_path in [StatePath, ProgramStatePath]:
            if state_path:
                sp = Path(state_path)
                if sp.parent.exists():
                    try:
                        state_target = str((sp.parent / sp.name).resolve())
                        if os.path.normcase(target_path) == os.path.normcase(state_target):
                            write_runlog("INFO", f"[DRY RUN] skip state write: {target_path}")
                            return
                    except Exception:
                        pass
    value["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    json_text = json.dumps(value, indent=2, ensure_ascii=False, default=str)
    p.write_text(json_text + "\n", encoding="utf-8")


def write_run_summary(state=None, status="RUNNING"):
    global LastRunSummary, RunStamp, WorkerId, RunLogDir, LatestFile, LatestRoundName, LatestRoleName, LatestCallName, LatestCallDir
    summary = {
        "version": 1,
        "run_stamp": RunStamp,
        "worker_id": WorkerId,
        "status": status,
        "run_dir": RunLogDir,
        "run_log": LatestFile,
        "latest_txt": LatestFile,
        "latest_round": LatestRoundName,
        "latest_role": LatestRoleName,
        "latest_phase": LatestCallName,
        "latest_role_dir": LatestCallDir,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
    }
    if state:
        summary["branch"] = state.get("branch")
        summary["max_iterations"] = state.get("max_iterations")
        summary["current_round"] = state.get("current_round")
        summary["full_gate_every"] = state.get("full_gate_every")
        summary["last_result"] = state.get("last_result")
        summary["last_task_brief"] = state.get("last_task_brief")
        summary["last_receipt"] = state.get("last_receipt")
        summary["last_commit"] = state.get("last_commit")
    LastRunSummary = summary


def write_round_summary(round_dir, round_result, gate=None):
    global LastRoundSummary, RunStamp, WorkerId, LatestRoleName, LatestCallName, LatestCallDir
    if not round_dir or not Path(round_dir).exists():
        return
    summary = {
        "version": 1,
        "run_stamp": RunStamp,
        "worker_id": WorkerId,
        "round_dir": round_dir,
        "status": round_result.get("status", "UNKNOWN") if round_result else "UNKNOWN",
        "task_brief": round_result.get("task_brief") if round_result else None,
        "receipt": round_result.get("receipt") if round_result else None,
        "writer_role": round_result.get("writer_role") if round_result else None,
        "implementer_role": round_result.get("implementer_role") if round_result else None,
        "gate": gate or (round_result.get("gate") if round_result else None),
        "commit": round_result.get("commit") if round_result else None,
        "latest_role": LatestRoleName,
        "latest_phase": LatestCallName,
        "latest_role_dir": LatestCallDir,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
    }
    LastRoundSummary = summary


def resolve_optional_path(path):
    if not path:
        return ""
    return str(Path(path).resolve())


def read_optional_text_file(path, max_chars=12000):
    if not path or not Path(path).exists():
        return ""
    text = Path(path).read_text(encoding="utf-8")
    if len(text) > max_chars:
        return text[:max_chars] + "\n...[truncated by auto harness]..."
    return text


def get_git_short_status():
    result = subprocess.run(
        ["git", "status", "--short"],
        cwd=RepoRoot, capture_output=True, text=True, encoding="utf-8"
    )
    lines = result.stdout.splitlines()
    filtered = []
    for line in lines:
        if not line:
            continue
        path = line[3:].strip() if len(line) > 3 else line.strip()
        if path.startswith('"') and path.endswith('"'):
            path = path.strip('"')
        if filter_local_workspace_paths([path]):
            filtered.append(line)
    return filtered


def get_git_diff_names(*args):
    result = subprocess.run(
        ["git", "diff", "--name-only"] + list(args),
        cwd=RepoRoot, capture_output=True, text=True, encoding="utf-8"
    )
    names = result.stdout.strip().split("\n") if result.stdout.strip() else []
    return filter_local_workspace_paths([n for n in names if n])


# Join-ProcessArguments: build process argument list safely for Windows
# redirect_standard_error: capture git stderr as process output
# stderr captured via subprocess.PIPE to avoid shell NativeCommandError
def invoke_git_captured(*args):
    proc = subprocess.run(
        ["git"] + list(args),
        cwd=RepoRoot, capture_output=True, text=True, encoding="utf-8"
    )
    lines = []
    if proc.stdout:
        lines.extend(l for l in proc.stdout.split("\n") if l)
    if proc.stderr:
        lines.extend(l for l in proc.stderr.split("\n") if l)
    return {"exit_code": proc.returncode, "output": lines}


def invoke_command_string(command_string, log_path="", round_dir="", label="COMMAND"):
    write_runlog("INFO", f"run: {command_string}")
    try:
        proc = subprocess.run(
            command_string,
            cwd=RepoRoot,
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        text = proc.stdout
        if proc.stderr:
            text = (text + "\n" + proc.stderr) if text else proc.stderr
        if log_path:
            Path(log_path).write_text(text, encoding="utf-8")
        ok = proc.returncode == 0
        result = {"ok": ok, "exit_code": proc.returncode, "output": text}
        add_command_console_log(command_string, result, round_dir, label)
        return result
    except Exception as e:
        text = str(e)
        if log_path:
            Path(log_path).write_text(text, encoding="utf-8")
        result = {"ok": False, "exit_code": 1, "output": text}
        add_command_console_log(command_string, result, round_dir, label)
        return result


def test_role_health(config, role_name, enable_role_health_check=False):
    role = config.get("roles", {}).get(role_name)
    if not role:
        return False
    if not enable_role_health_check:
        write_runlog("INFO", f"role health check skipped role={role_name}")
        return True
    if not role.get("health_command"):
        return True
    write_runlog("INFO", f"health check role={role_name} command={role['health_command']}")
    result = invoke_command_string(role["health_command"], label=f"health role={role_name}")
    if not result["ok"]:
        write_runlog("WARN", f"role health failed: {role_name} exit={result['exit_code']}")
    return result["ok"]


def _test_env_name(name):
    return bool(re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", name))


def _get_default_env_name(kind, is_anthropic):
    if kind == "base":
        return "ANTHROPIC_BASE_URL" if is_anthropic else "OPENAI_BASE_URL"
    if kind == "key":
        return "ANTHROPIC_API_KEY" if is_anthropic else "OPENAI_API_KEY"
    if kind == "auth":
        return "ANTHROPIC_AUTH_TOKEN"
    if kind == "model":
        return "ANTHROPIC_MODEL" if is_anthropic else "OPENAI_MODEL"
    return kind


def _get_conflicting_env_names(is_anthropic):
    if is_anthropic:
        return ["OPENAI_BASE_URL", "OPENAI_API_KEY", "OPENAI_MODEL"]
    return ["ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_MODEL"]


def _resolve_configured_binding(default_env, config_value):
    if config_value is None:
        return {"env": default_env, "value": None}
    if isinstance(config_value, str):
        if _test_env_name(config_value):
            return {"env": config_value, "value": os.environ.get(config_value)}
        return {"env": default_env, "value": config_value}
    if isinstance(config_value, dict):
        env_name = config_value.get("env", default_env)
        if not _test_env_name(env_name):
            env_name = default_env
        value = None
        if "env" in config_value:
            source = str(config_value["env"])
            if "value" in config_value and config_value["value"]:
                value = config_value["value"]
            elif _test_env_name(source):
                value = os.environ.get(source)
            else:
                value = source
        elif "value" in config_value:
            value = config_value["value"]
        return {"env": env_name, "value": value}
    return {"env": default_env, "value": str(config_value)}


# Get-ProviderFamily: distinguish OpenAI and Anthropic providers
def get_provider_family(provider_name, provider):
    if provider and provider.get("family"):
        return str(provider["family"]).lower()
    if provider_name and re.search(r"claude|anthropic|glm", provider_name, re.IGNORECASE):
        return "anthropic"
    return "openai"


def set_provider_environment(config, role, command=""):
    provider_name = role.get("provider", "")
    if not provider_name:
        return {}
    provider = config.get("providers", {}).get(provider_name, {})
    if not provider:
        return {}
    provider_family = get_provider_family(provider_name, provider)
    is_claude_command = (command == "claude")

    is_anthropic = (provider_family == "anthropic" or is_claude_command)

    base_config = provider.get("base_url")
    if not base_config and provider.get("env"):
        if is_claude_command and provider["env"].get("OPENAI_BASE_URL"):
            base_config = provider["env"]["OPENAI_BASE_URL"]
        elif provider["env"].get("ANTHROPIC_BASE_URL"):
            base_config = provider["env"]["ANTHROPIC_BASE_URL"]
    key_config = provider.get("api_key")
    if not key_config and provider.get("env"):
        if is_claude_command and provider["env"].get("OPENAI_API_KEY"):
            key_config = provider["env"]["OPENAI_API_KEY"]
        elif provider["env"].get("ANTHROPIC_API_KEY"):
            key_config = provider["env"]["ANTHROPIC_API_KEY"]
    auth_config = provider.get("auth_token")
    if not auth_config and provider.get("env"):
        if provider["env"].get("ANTHROPIC_AUTH_TOKEN"):
            auth_config = provider["env"]["ANTHROPIC_AUTH_TOKEN"]
        elif is_claude_command and provider["env"].get("OPENAI_API_KEY"):
            auth_config = provider["env"]["OPENAI_API_KEY"]

    base_binding = _resolve_configured_binding(_get_default_env_name("base", is_anthropic), base_config)
    if not base_binding.get("value") and provider.get("base_url_env"):
        base_binding = _resolve_configured_binding(_get_default_env_name("base", is_anthropic), provider["base_url_env"])
    key_binding = _resolve_configured_binding(_get_default_env_name("key", is_anthropic), key_config)
    if not key_binding.get("value") and provider.get("api_key_env"):
        key_binding = _resolve_configured_binding(_get_default_env_name("key", is_anthropic), provider["api_key_env"])
    auth_binding = _resolve_configured_binding(_get_default_env_name("auth", is_anthropic), auth_config)
    if not auth_binding.get("value") and provider.get("auth_token_env"):
        auth_binding = _resolve_configured_binding(_get_default_env_name("auth", is_anthropic), provider["auth_token_env"])
    model_binding = _resolve_configured_binding(_get_default_env_name("model", is_anthropic), provider.get("model"))
    if not model_binding.get("value") and provider.get("model_env"):
        model_binding = _resolve_configured_binding(_get_default_env_name("model", is_anthropic), provider["model_env"])

    old = {}
    for env_name in [base_binding["env"], key_binding["env"], auth_binding["env"], model_binding["env"]]:
        if env_name:
            old[env_name] = os.environ.get(env_name)

    for env_name in _get_conflicting_env_names(is_anthropic):
        if env_name:
            if env_name not in old:
                old[env_name] = os.environ.get(env_name)
            os.environ.pop(env_name, None)

    if base_binding.get("env") and base_binding.get("value"):
        os.environ[base_binding["env"]] = base_binding["value"]
    if key_binding.get("env") and key_binding.get("value"):
        os.environ[key_binding["env"]] = key_binding["value"]
    if auth_binding.get("env") and auth_binding.get("value"):
        os.environ[auth_binding["env"]] = auth_binding["value"]
    if model_binding.get("env") and model_binding.get("value"):
        os.environ[model_binding["env"]] = model_binding["value"]

    if provider.get("env"):
        for env_name, env_val in provider["env"].items():
            if is_claude_command and env_name.startswith("OPENAI_"):
                continue
            env_binding = _resolve_configured_binding(env_name, env_val)
            if env_binding.get("env") and env_binding.get("value"):
                old[env_binding["env"]] = os.environ.get(env_binding["env"])
                os.environ[env_binding["env"]] = env_binding["value"]

    if provider.get("headers"):
        for header_name, header_spec in provider["headers"].items():
            if header_spec is None:
                continue
            header_env = "CLAUDE_HEADER_" + re.sub(r"[^A-Za-z0-9_]", "_", header_name).upper()
            header_value = None
            if isinstance(header_spec, dict):
                if header_spec.get("value"):
                    header_value = header_spec["value"]
                elif header_spec.get("env") and _test_env_name(header_spec["env"]):
                    header_value = os.environ.get(header_spec["env"])
                elif header_spec.get("env"):
                    header_value = header_spec["env"]
            elif isinstance(header_spec, str):
                if _test_env_name(header_spec):
                    header_value = os.environ.get(header_spec)
                else:
                    header_value = header_spec
            if header_value:
                old[header_env] = os.environ.get(header_env)
                os.environ[header_env] = header_value

    return old


def restore_provider_environment(old_values):
    for name, value in old_values.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value


def get_role_configured_model(config, role):
    if not role.get("provider"):
        return ""
    provider = config.get("providers", {}).get(role["provider"], {})
    if not provider:
        return ""
    if provider.get("model"):
        return str(provider["model"])
    if provider.get("model_env"):
        return str(os.environ.get(str(provider["model_env"]), ""))
    return ""


def add_claude_model_arg(cli_args, model):
    if not model:
        return list(cli_args)
    for arg in cli_args:
        if str(arg) == "--model" or str(arg).startswith("--model="):
            return list(cli_args)
    return ["--model", model] + list(cli_args)


def resolve_role_cli_args(config, role):
    cli_args = list(role.get("args", []))
    if role.get("command", "claude") != "claude":
        return cli_args
    return add_claude_model_arg(cli_args, get_role_configured_model(config, role))


# Set-ClaudeProjectSettings: override project Claude settings per role
def set_claude_project_settings(config, role, model):
    global RepoRoot
    if not role.get("provider"):
        return None
    provider_name = str(role["provider"])
    provider = config.get("providers", {}).get(provider_name, {})
    if not provider:
        return None
    family = get_provider_family(provider_name, provider)
    if family == "openai":
        family = "anthropic"
    settings_path = os.path.join(RepoRoot, ".claude", "settings.local.json")
    settings_dir = os.path.dirname(settings_path)
    os.makedirs(settings_dir, exist_ok=True)

    backup = {"path": settings_path, "existed": os.path.exists(settings_path), "content": None}
    settings = {}
    if backup["existed"]:
        try:
            backup["content"] = Path(settings_path).read_text(encoding="utf-8")
            settings = json.loads(backup["content"])
        except Exception:
            settings = {}

    preserved_settings = {}
    if settings and settings.get("permissions"):
        preserved_settings["permissions"] = settings["permissions"]

    # $providerFamily -eq "anthropic"
    if family == "anthropic":
        preserved_settings["env"] = {
            "ANTHROPIC_BASE_URL": os.environ.get("ANTHROPIC_BASE_URL"),
            "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY"),
            "ANTHROPIC_AUTH_TOKEN": os.environ.get("ANTHROPIC_AUTH_TOKEN"),
            "ANTHROPIC_MODEL": os.environ.get("ANTHROPIC_MODEL"),
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": model if model else os.environ.get("ANTHROPIC_DEFAULT_HAIKU_MODEL"),
            "ANTHROPIC_DEFAULT_SONNET_MODEL": model if model else os.environ.get("ANTHROPIC_DEFAULT_SONNET_MODEL"),
            "ANTHROPIC_DEFAULT_OPUS_MODEL": model if model else os.environ.get("ANTHROPIC_DEFAULT_OPUS_MODEL"),
        }
        preserved_settings["model"] = "opus"
    else:
        preserved_settings["env"] = {
            "OPENAI_BASE_URL": os.environ.get("OPENAI_BASE_URL"),
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "OPENAI_MODEL": os.environ.get("OPENAI_MODEL"),
        }

    json_text = json.dumps(preserved_settings, indent=2, ensure_ascii=False, default=str)
    Path(settings_path).write_text(json_text, encoding="utf-8")
    return backup


def restore_claude_project_settings(backup):
    if not backup or not backup.get("path"):
        return
    if backup["existed"]:
        Path(backup["path"]).write_text(str(backup["content"]), encoding="utf-8")
    elif os.path.exists(backup["path"]):
        os.remove(backup["path"])


def resolve_agent_timeout_seconds(config, role):
    if "timeout_seconds" in role and role["timeout_seconds"] is not None:
        ts = int(role["timeout_seconds"])
        if ts > 0:
            return ts
    defaults = config.get("defaults", {})
    if defaults and "agent_timeout_seconds" in defaults and defaults["agent_timeout_seconds"] is not None:
        ts = int(defaults["agent_timeout_seconds"])
        if ts > 0:
            return ts
    return 900


def resolve_process_command(command):
    resolved = shutil.which(command)
    return resolved if resolved else command


def invoke_agent_role(config, role_name, prompt, round_log_dir, call_kind="main", enable_role_health_check=False):
    global DryRun, AgentDisplayBuffer, AgentStepCounts, AgentDisplayEmitHost, LatestRoleName, LatestCallName, LatestCallDir, LatestRoundName

    selected_role_name = role_name
    role = config.get("roles", {}).get(selected_role_name, {})
    if not role:
        raise RuntimeError(f"[auto-harness] missing role config: {selected_role_name}")
    if not test_role_health(config, selected_role_name, enable_role_health_check):
        raise RuntimeError(f"[auto-harness] role health failed: {selected_role_name}")

    command = role.get("command", "claude")
    configured_model = get_role_configured_model(config, role)
    cli_args = resolve_role_cli_args(config, role)

    command_path = resolve_process_command(command)
    archived_script_suffix = "." + "ps1"
    if command_path.endswith(archived_script_suffix):
        raise RuntimeError(
            f"[auto-harness] archived script role commands are no longer supported: {command_path}"
        )

    call_info = new_agent_call_directory(round_log_dir, selected_role_name, call_kind)
    role_dir = call_info["role_dir"]
    phase_name = call_info["phase"]
    round_name = os.path.basename(round_log_dir)
    set_latest_call_path(role_dir, round_name, selected_role_name, phase_name)
    display_log = os.path.join(role_dir, "console.log")
    timeout_seconds = resolve_agent_timeout_seconds(config, role)
    env_backup = set_provider_environment(config, role, command)
    settings_backup = set_claude_project_settings(config, role, configured_model) if command == "claude" else None

    try:
        write_runlog("INFO", f"invoke role={selected_role_name} phase={phase_name} command={command}")
        tool_count = 0
        api_limited = False
        balance_exhausted = False
        timed_out = False
        started_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        captured_lines = []
        captured_payloads = []
        role_console_path = os.path.join(role_dir, "console.log")
        start_block = (
            "\r\n"
            "################################################################################\r\n"
            f"role={selected_role_name} phase={phase_name} started={started_iso}\r\n"
            "################################################################################\r\n"
            "[COMMAND]\r\n"
            f"{command_path} {' '.join(str(a) for a in cli_args)}\r\n"
            "\r\n"
            f"[TIMEOUT_SECONDS]\r\n"
            f"{'none' if timeout_seconds is None else timeout_seconds}"
        )
        ensure_dir(Path(role_dir))
        with open(role_console_path, "a", encoding="utf-8") as f:
            f.write(start_block + "\r\n")

        if DryRun:
            dry_text = f"[DRY RUN] {prompt}"
            add_agent_aggregate_console_log(dry_text, role_dir, round_log_dir, selected_role_name, phase_name)
            return {"ok": True, "role": selected_role_name, "exit_code": 0, "tool_count": 0,
                    "log": display_log, "console": display_log, "role_dir": role_dir, "phase": phase_name}

        started_at = time.time()
        previous_display_buffer = AgentDisplayBuffer
        AgentDisplayBuffer = captured_lines
        initial_step_count = AgentStepCounts.get(selected_role_name, 0)
        AgentStepCounts[selected_role_name] = initial_step_count

        try:
            print_host("")
            print_host("==================================================", "darkcyan")
            print_host(f"  AI role: {selected_role_name}", "cyan")
            print_host("==================================================", "darkcyan")
            write_agent_display_log_line(selected_role_name, "==================================================")
            write_agent_display_log_line(selected_role_name, f"AI role: {selected_role_name}")
            write_agent_display_log_line(selected_role_name, "==================================================")

            # Build escaped args string for subprocess
            escaped_args = []
            for arg in cli_args:
                arg_text = str(arg)
                if " " in arg_text or '"' in arg_text:
                    arg_text = '"' + arg_text.replace('"', '\\"') + '"'
                escaped_args.append(arg_text)
            args_str = " ".join(escaped_args)

            proc = subprocess.Popen(
                [command_path] + [args_str] if not args_str else [command_path] + cli_args,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=RepoRoot,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )

            # Write prompt to stdin
            try:
                proc.stdin.write((prompt + "\n").encode("utf-8"))
                proc.stdin.close()
            except Exception:
                pass

            deadline = time.time() + timeout_seconds if timeout_seconds is not None else None

            stdout_lines = []
            stderr_lines = []

            def read_stdout():
                try:
                    for raw_line in proc.stdout:
                        try:
                            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                        except Exception:
                            line = raw_line.rstrip(b"\r\n").decode("utf-8", errors="replace")
                        stdout_lines.append(line)
                except Exception:
                    pass

            def read_stderr():
                try:
                    for raw_line in proc.stderr:
                        try:
                            line = raw_line.decode("utf-8", errors="replace").rstrip("\r\n")
                        except Exception:
                            line = raw_line.rstrip(b"\r\n").decode("utf-8", errors="replace")
                        stderr_lines.append(line)
                except Exception:
                    pass

            t_out = threading.Thread(target=read_stdout, daemon=True)
            t_err = threading.Thread(target=read_stderr, daemon=True)
            t_out.start()
            t_err.start()

            last_stdout_idx = 0
            last_stderr_idx = 0
            while True:
                # Process new stdout lines
                while last_stdout_idx < len(stdout_lines):
                    line = stdout_lines[last_stdout_idx]
                    last_stdout_idx += 1
                    captured_payloads.append(line)
                    write_agent_stream_line(selected_role_name, "stdout", line)
                # Process new stderr lines
                while last_stderr_idx < len(stderr_lines):
                    line = stderr_lines[last_stderr_idx]
                    last_stderr_idx += 1
                    captured_payloads.append(line)
                    write_agent_stream_line(selected_role_name, "stderr", line)

                if proc.poll() is not None and last_stdout_idx >= len(stdout_lines) and last_stderr_idx >= len(stderr_lines):
                    break

                if deadline and time.time() > deadline:
                    timed_out = True
                    try:
                        proc.kill()
                    except Exception:
                        pass
                    break

                time.sleep(0.05)

            t_out.join(timeout=2)
            t_err.join(timeout=2)

            exit_code = 1 if timed_out else proc.returncode
            if timed_out:
                write_agent_display_log_line(selected_role_name, "")
                write_agent_display_log_line(selected_role_name, f"  [TIMEOUT] after {timeout_seconds}s")
                write_runlog("WARN", f"agent role={selected_role_name} timed out after {timeout_seconds}s")
            write_agent_display_log_line(selected_role_name, f"  [__AUTO_HARNESS_EXIT_CODE:{exit_code}]")
            call_text = "\r\n".join(captured_lines)
            add_agent_aggregate_console_log(call_text, role_dir, round_log_dir, selected_role_name, phase_name)
            write_runlog("INFO", f"agent role={selected_role_name} phase={phase_name} exit_code={exit_code} console={display_log}")

        except Exception as e:
            exit_code = 1
            write_agent_display_log_line(selected_role_name, "")
            write_agent_display_log_line(selected_role_name, f"  [EXCEPTION] {e}")
            write_agent_display_log_line(selected_role_name, "  [__AUTO_HARNESS_EXIT_CODE:1]")
            call_text = "\r\n".join(captured_lines)
            add_agent_aggregate_console_log(call_text, role_dir, round_log_dir, selected_role_name, phase_name)
            write_runlog("ERROR", f"agent role={selected_role_name} exception={e}")
        finally:
            AgentDisplayBuffer = previous_display_buffer

        for line_for_analysis in captured_payloads:
            try:
                evt = json.loads(line_for_analysis)
                if evt.get("type") == "assistant" and evt.get("message", {}).get("content"):
                    for part in evt["message"]["content"]:
                        if part.get("type") == "tool_use":
                            tool_count += 1
            except Exception:
                if re.search(r"429|rate_limit", line_for_analysis):
                    api_limited = True
                if re.search(r"402|Insufficient Balance|insufficient_balance", line_for_analysis):
                    balance_exhausted = True

        completed_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        output_text = "\n".join(captured_lines + captured_payloads)
        return {
            "ok": exit_code == 0 and not balance_exhausted and not timed_out,
            "role": selected_role_name,
            "phase": phase_name,
            "role_dir": role_dir,
            "exit_code": exit_code,
            "tool_count": tool_count,
            "api_limited": api_limited,
            "balance_exhausted": balance_exhausted,
            "timed_out": timed_out,
            "console": display_log,
            "output_text": output_text,
            "started_at": started_iso,
            "completed_at": completed_iso,
        }
    finally:
        restore_claude_project_settings(settings_backup)
        restore_provider_environment(env_backup)


def should_stop_after_writer_failure(writer, resolved_task_brief_path=""):
    if writer.get("ok"):
        return False
    if resolved_task_brief_path:
        return False
    return writer.get("role") == "task_writer"


def build_epic_alignment_gate_command(task_brief, epic_contract):
    script = str(Path("harness-engine") / ".dev-harness" / "checks" / "epic_alignment_gate.py")
    return subprocess.list2cmdline([
        sys.executable,
        script,
        "--TaskBrief",
        str(task_brief),
        "--EpicContract",
        str(epic_contract),
    ])


def get_structured_backlog_path(epic_root, backlog_path):
    if epic_root:
        candidate = Path(epic_root) / "backlog.json"
        if candidate.exists():
            return str(candidate.resolve())
    if backlog_path:
        candidate = Path(str(backlog_path)).with_suffix(".json")
        if candidate.exists():
            return str(candidate.resolve())
    return ""


def build_rolling_planner_command(epic_contract, backlog_json, output_spec):
    script = str(Path("harness-engine") / ".dev-harness" / "scripts" / "rolling_task_planner.py")
    return subprocess.list2cmdline([
        sys.executable,
        script,
        "--EpicContract",
        str(epic_contract),
        "--Backlog",
        str(backlog_json),
        "--OutputSpec",
        str(output_spec),
    ])


def prepare_rolling_task_spec(epic):
    global AutomationRoot, RunStamp
    if not epic.get("enabled") or epic.get("complete"):
        return ""
    contract_path = epic.get("contract_path")
    backlog_json = epic.get("backlog_json_path")
    if not contract_path or not backlog_json:
        return ""
    planner_dir = Path(AutomationRoot) / "planner"
    ensure_dir(planner_dir)
    output_spec = planner_dir / f"next-task-{RunStamp or 'current'}.json"
    result = invoke_command_string(
        build_rolling_planner_command(contract_path, backlog_json, output_spec),
        label="rolling-task-planner",
    )
    if not result.get("ok"):
        write_runlog("WARN", f"rolling task planner could not prepare next spec: {str(result.get('output', ''))[:200]}")
        return ""
    return str(output_spec.resolve())


def invoke_programmatic_task_writer(spec_path, round_dir):
    command = subprocess.list2cmdline([
        sys.executable,
        str(Path("harness-engine") / ".dev-harness" / "scripts" / "new_task_brief.py"),
        "--SpecFile",
        str(spec_path),
    ])
    result = invoke_command_string(command, round_dir=round_dir, label="programmatic-task-writer")
    return {
        "ok": bool(result.get("ok")),
        "role": "programmatic_task_writer",
        "exit_code": result.get("exit_code", 0),
        "tool_count": 0,
        "log": result.get("output", ""),
        "console": result.get("output", ""),
    }


def preflight_output_reports_blocked_precheck(output_text):
    in_result = False
    for raw_line in str(output_text or "").splitlines():
        line = raw_line.strip()
        if line == "[RESULT]" or line.endswith(" [RESULT]"):
            in_result = True
            continue
        if line.startswith("[__AUTO_HARNESS_EXIT_CODE:"):
            in_result = False
            continue
        if in_result and re.search(r"(?i)^(status|result|verdict)?\s*:?\s*BLOCKED_PRECHECK\b", line):
            return True
    return False


def new_auto_state(max_iterations, branch, auto_push, full_gate_every):
    global WorkerId, RepoRoot
    current_branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=RepoRoot, capture_output=True, text=True, encoding="utf-8"
    ).stdout.strip()
    return {
        "version": 1,
        "status": "RUNNING",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
        "worker_id": WorkerId,
        "branch": branch,
        "base_branch": current_branch,
        "max_iterations": max_iterations,
        "current_round": 0,
        "full_gate_every": full_gate_every,
        "auto_push": auto_push,
        "preflight": {"status": "NOT_RUN", "commit": None, "log_dir": None, "gate_result": None},
        "rounds": [],
        "last_result": None,
        "last_task_brief": None,
        "last_receipt": None,
        "last_commit": None,
        "last_error": None,
    }


def new_program_state():
    global WorkerId
    return {
        "version": 1,
        "status": "IDLE",
        "active_epic": None,
        "epics": [],
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
    }


def get_epic_contract(path):
    if not path or not Path(path).exists():
        return None
    return read_json_file(path)


def test_epic_contract_complete(contract):
    if not contract:
        return False
    if str(contract.get("status", "")) == "complete":
        return True
    items = contract.get("acceptance_items", [])
    if not items:
        return False
    open_items = [i for i in items if str(i.get("status", "")) not in ("done", "complete")]
    return len(open_items) == 0


def resolve_epic_context(requested_epic_id, requested_epic_root, requested_contract_path,
                         requested_goal_path, requested_design_path, requested_backlog_path):
    global AutomationRoot, ProgramStatePath
    program = read_json_file(ProgramStatePath) if Path(ProgramStatePath).exists() else new_program_state()
    if not program.get("epics"):
        program["epics"] = []

    resolved_root = ""
    if requested_epic_root:
        resolved_root = str(Path(requested_epic_root).resolve())
    elif requested_epic_id:
        candidate = os.path.join(AutomationRoot, "epics", requested_epic_id)
        if Path(candidate).exists():
            resolved_root = str(Path(candidate).resolve())
    elif program.get("active_epic"):
        candidate = os.path.join(AutomationRoot, "epics", program["active_epic"])
        if Path(candidate).exists():
            resolved_root = str(Path(candidate).resolve())

    contract_path = resolve_optional_path(requested_contract_path) if requested_contract_path else (
        os.path.join(resolved_root, "contract.json") if resolved_root else "")
    goal_path = resolve_optional_path(requested_goal_path) if requested_goal_path else (
        os.path.join(resolved_root, "goal.md") if resolved_root else "")
    design_path = resolve_optional_path(requested_design_path) if requested_design_path else (
        os.path.join(resolved_root, "design.md") if resolved_root else "")
    backlog_path = resolve_optional_path(requested_backlog_path) if requested_backlog_path else (
        os.path.join(resolved_root, "backlog.md") if resolved_root else "")
    backlog_json_path = get_structured_backlog_path(resolved_root, backlog_path)

    contract = get_epic_contract(contract_path)
    resolved_epic_id = requested_epic_id
    if not resolved_epic_id and contract and contract.get("epic_id"):
        resolved_epic_id = contract["epic_id"]
    if not resolved_epic_id and program.get("active_epic"):
        resolved_epic_id = program["active_epic"]

    if resolved_epic_id:
        program["status"] = "RUNNING"
        program["active_epic"] = resolved_epic_id
        existing = [e for e in program.get("epics", []) if e.get("id") == resolved_epic_id]
        if not existing:
            program["epics"] = program.get("epics", []) + [{
                "id": resolved_epic_id,
                "status": "active",
                "root": resolved_root if resolved_root else None,
                "contract": contract_path if contract_path else None,
                "branch": None,
                "current_round": 0,
                "last_result": None,
            }]
        write_json_file(ProgramStatePath, program)

    design_doc_files = []
    if resolved_root:
        designs_dir = os.path.join(resolved_root, "designs")
        if os.path.isdir(designs_dir):
            for fname in sorted(os.listdir(designs_dir)):
                fpath = os.path.join(designs_dir, fname)
                if os.path.isfile(fpath):
                    design_doc_files.append({"name": fname, "path": fpath})

    return {
        "enabled": bool(resolved_epic_id),
        "complete": test_epic_contract_complete(contract),
        "id": resolved_epic_id,
        "root": resolved_root,
        "contract_path": contract_path,
        "contract": contract,
        "goal_path": goal_path,
        "design_path": design_path,
        "backlog_path": backlog_path,
        "backlog_json_path": backlog_json_path,
        "goal_text": read_optional_text_file(goal_path),
        "design_text": read_optional_text_file(design_path),
        "backlog_text": read_optional_text_file(backlog_path),
        "planner_spec_path": "",
        "design_doc_files": design_doc_files,
    }


# Resolve-NextEpicContext: resolve next epic continuation from a completed contract
def resolve_next_epic_context(epic):
    global AutomationRoot, RepoRoot
    if not epic.get("enabled") or not epic.get("complete") or not epic.get("contract"):
        return None
    next_epic = epic["contract"].get("next_epic")
    if not next_epic:
        return None

    next_epic_id = ""
    next_epic_root = ""
    if isinstance(next_epic, str):
        next_epic_id = str(next_epic)
    else:
        next_epic_id = str(next_epic.get("id", ""))
        next_epic_root = str(next_epic.get("root", ""))
    if not next_epic_id and not next_epic_root:
        return None
    if not next_epic_root and next_epic_id:
        next_epic_root = os.path.join(AutomationRoot, "epics", next_epic_id)
    if next_epic_root and not os.path.isabs(next_epic_root):
        next_epic_root = os.path.join(RepoRoot, next_epic_root)
    if next_epic_root and not Path(next_epic_root).exists():
        write_runlog("WARN", f"completed epic declares next_epic but root is missing: {next_epic_root}")
        return None

    return resolve_epic_context(next_epic_id, next_epic_root, "", "", "", "")


def guard_completed_epic_before_preflight(epic, state, resolved_task_brief_path):
    if not (epic.get("enabled") and epic.get("complete") and not resolved_task_brief_path):
        return {"handled": False, "epic": epic}

    next_epic = resolve_next_epic_context(epic)
    if next_epic and next_epic.get("enabled") and not next_epic.get("complete"):
        # completed epic advanced to next_epic
        write_runlog("INFO", f"completed epic advanced to next_epic before preflight: {epic.get('id')} -> {next_epic.get('id')}")
        state["last_result"] = "EPIC_COMPLETE_ADVANCED_TO_NEXT"
        state["last_error"] = None
        write_json_file(StatePath, state)
        write_run_summary(state, "EPIC_COMPLETE_ADVANCED_TO_NEXT")
        return {"handled": False, "epic": next_epic}

    write_runlog("WARN", f"active epic contract is complete; stopping before preflight/task_writer to avoid repair spiral: {epic.get('id')}")
    hint = get_research_resume_hint().replace("\r\n", " | ").replace("\n", " | ")
    write_runlog("INFO", hint)
    state["status"] = "EPIC_COMPLETE_NEEDS_NEXT_RESEARCH_EPIC"
    state["last_result"] = "EPIC_COMPLETE"
    state["last_error"] = "completed epic should not run preflight or generate another repair task"
    write_json_file(StatePath, state)
    write_run_summary(state, state["status"])
    return {"handled": True, "epic": epic}


def update_program_round_state(epic, state, round_result):
    global ProgramStatePath
    if not epic.get("enabled") or not Path(ProgramStatePath).exists():
        return
    program = read_json_file(ProgramStatePath)
    updated_epics = []
    for entry in program.get("epics", []):
        if entry.get("id") == epic.get("id"):
            entry["status"] = "active"
            entry["branch"] = state.get("branch")
            entry["current_round"] = state.get("current_round")
            entry["last_result"] = state.get("last_result")
            entry["latest_task"] = state.get("last_task_brief")
            entry["latest_receipt"] = state.get("last_receipt")
            entry["latest_commit"] = state.get("last_commit")
            entry["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        updated_epics.append(entry)
    program["epics"] = updated_epics
    program["active_epic"] = epic.get("id")
    program["status"] = "RUNNING"
    write_json_file(ProgramStatePath, program)


def write_trace_summary(round_dir, epic, round_result, gate):
    global LastTraceSummary, RunStamp, WorkerId
    summary = {
        "version": 1,
        "run_stamp": RunStamp,
        "worker_id": WorkerId,
        "epic_id": epic.get("id") if epic.get("enabled") else None,
        "task_brief": round_result.get("task_brief"),
        "receipt": round_result.get("receipt"),
        "status": round_result.get("status"),
        "gate": gate,
        "writer_role": round_result.get("writer_role"),
        "implementer_role": round_result.get("implementer_role"),
        "log_dir": round_dir,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
    }
    LastTraceSummary = summary


def get_latest_task_brief():
    global RepoRoot
    task_dir = Path(RepoRoot) / "harness-engine" / ".dev-harness" / "task-briefs"
    if not task_dir.exists():
        return None
    tasks = sorted(task_dir.glob("*.md"), key=lambda p: p.name)
    return str(tasks[-1].resolve()) if tasks else None


def resolve_task_brief_path(path):
    global RepoRoot, DryRun
    if not path:
        return None
    full_path = str(Path(path).resolve())
    task_root = str(Path(RepoRoot) / "harness-engine" / ".dev-harness" / "task-briefs").lower()
    tmp_root_path = Path(RepoRoot) / "harness-engine" / ".dev-harness" / "tmp"
    tmp_root = str(tmp_root_path.resolve()).lower() if tmp_root_path.exists() else None
    full_lower = full_path.lower()
    under_task_root = full_lower.startswith(task_root)
    under_tmp_root = DryRun and tmp_root and full_lower.startswith(tmp_root)
    if not under_task_root and not under_tmp_root:
        raise RuntimeError("[auto-harness] TaskBriefPath must be under harness-engine/.dev-harness/task-briefs")
    if not full_path.lower().endswith(".md"):
        raise RuntimeError("[auto-harness] TaskBriefPath must point to a markdown task brief")
    return full_path


def get_task_status(path):
    if not path or not Path(path).exists():
        return "UNKNOWN"
    content = Path(path).read_text(encoding="utf-8")
    m = re.search(r"(?im)^\s*Task Status:\s*(?P<status>[A-Z_]+)\s*$", content)
    return m.group("status").strip() if m else "UNKNOWN"


def get_task_epic_id(path):
    if not path or not Path(path).exists():
        return ""
    content = Path(path).read_text(encoding="utf-8")
    return normalize_inline_value(get_field_value(content, "Epic ID"))


# Test-TaskMatchesEpic: verify resumed tasks match the active epic
def test_task_matches_epic(task_brief, epic):
    if not epic.get("enabled"):
        return True
    if not task_brief:
        return False
    task_epic_id = get_task_epic_id(task_brief)
    return bool(task_epic_id and task_epic_id == epic.get("id"))


def get_task_brief_text(path, max_chars=12000):
    return read_optional_text_file(path, max_chars)


def test_external_workspace_repair_task(path):
    text = get_task_brief_text(path, max_chars=16000)
    if not text:
        return False
    title_or_intent = ""
    title_match = re.search(r"(?im)^\s*#\s+(?P<title>.+?)\s*$", text)
    if title_match:
        title_or_intent += " " + title_match.group("title")
    intent_match = re.search(r"(?is)^\s*##\s+Intent\s*\r?\n(?P<intent>.*?)(?:\r?\n##\s+|\Z)", text)
    if intent_match:
        title_or_intent += " " + intent_match.group("intent")
    goal_match = re.search(r"(?is)^\s*##\s+Goal\s*\r?\n(?P<goal>.*?)(?:\r?\n##\s+|\Z)", text)
    if goal_match:
        title_or_intent += " " + goal_match.group("goal")
    # TitleOrIntent: distinguish repair intent from forbidden path mentions.
    # Ordinary same-epic repair tasks are valid; only local control-plane or
    # external-workspace cleanup should be rejected automatically.
    return bool(re.search(
        r"(?i)(scope blocker|external[- ]workspace|claude worktree|\.claude|settings\.local\.json|agent-\*)",
        title_or_intent,
    ))


def test_auto_external_workspace_repair_rejected(task_brief, task_status, explicit_task):
    if explicit_task:
        return False
    if task_status not in ("UNCLAIMED", "CLAIMED"):
        return False
    return test_external_workspace_repair_task(task_brief)


def get_recent_repair_task_run(recent=7):
    global RepoRoot
    task_dir = Path(RepoRoot) / "harness-engine" / ".dev-harness" / "task-briefs"
    if not task_dir.exists():
        return []
    tasks = sorted(task_dir.glob("*.md"), key=lambda p: p.name, reverse=True)[:recent]
    repair_like = []
    for task in tasks:
        text = get_task_brief_text(str(task), max_chars=16000)
        if re.search(r"(?im)^##\s+Run Type\s*\r?\n\s*REPAIR\b", text) or re.search(r"(?i)repair|scope-blocker|external-workspace", task.name):
            repair_like.append(str(task.resolve()))
    return repair_like


def test_repair_spiral_risk():
    return len(get_recent_repair_task_run(7)) >= 4


def get_research_resume_hint():
    return (
        "Research resume target:\n"
        "- Do not create another .claude/external-workspace repair task.\n"
        "- Treat .claude/settings.local.json and .claude/worktrees/agent-* as local environment blockers outside the structure-proof research stream.\n"
        "- If a task must be written, return to event-collection progress:\n"
        "  microstructure data feasibility -> schema -> 30d pilot backfill -> V4 cross-variable surrogate.\n"
        "- Keep NO_TRADE / RESEARCH_ONLY and do not claim tradable edge.\n"
    )


def get_task_number_from_path(path):
    if not path:
        return None
    name = os.path.basename(path)
    m = re.match(r"^(?P<number>\d{3})-", name)
    return int(m.group("number")) if m else None


def test_preflight_gate_can_continue(gate):
    global ResumeTaskBriefPath
    if not gate or gate.get("ok"):
        return False
    return False


def get_gate_output_excerpt(output, max_chars=4000):
    if not output:
        return "(no output)"
    text = str(output)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated by auto harness]..."


def get_gate_failure_class(gate):
    if not gate or gate.get("ok"):
        return "pass"
    output = str(gate.get("output", ""))
    if re.search(r"Acceptance Gate:\s+FAIL|Scenarios:\s+\d+\s+passed,\s+\d+\s+failed", output):
        return "product_acceptance"
    if re.search(r"\[receipt-gate\]", output):
        return "receipt_gate"
    if re.search(r"\[scope-diff-gate\]", output):
        return "scope_diff"
    if re.search(r"\[write-task-gate\]", output):
        return "write_task_gate"
    if re.search(r"\[epic-alignment-gate\]", output):
        return "epic_alignment"
    if re.search(r"\[memory-gate\]|\[memory-index\]", output):
        return "memory_gate"
    if re.search(r"\[programmatic-selftest\]", output):
        return "programmatic_selftest"
    if re.search(r"\[dev-gate\]\s+non-Rust product Python files found", output):
        return "product_python_scan"
    if re.search(r"\[dev-gate\]\s+(cargo fmt|cargo clippy|cargo test|Cargo\.toml|clippy component)", output):
        return "rust_product_gate"
    if re.search(r"(?m)^\s*(Checking|Compiling|Finished)\s+\S+", output) or re.search(r"(?m)^\s*error(\[|:)|cargo\s+(fmt|clippy|test)", output):
        return "rust_product_gate"
    if re.search(r"\[dev-gate\]", output):
        return "dev_gate_policy"
    return "unknown"


def test_implementer_repair_worth_running(gate, task_status):
    cls = get_gate_failure_class(gate)
    if task_status == "BLOCKED" and cls in ("scope_diff", "rust_product_gate", "product_python_scan", "dev_gate_policy", "unknown"):
        return False
    return True


def get_gate_repair_guidance(cls):
    if cls == "product_acceptance":
        return (
            "Acceptance gate failures are product/task failures first. Continue the current product task: inspect the "
            "scenario report, failed scenario names, first failed step, app routes/controllers/views, and service "
            "startup assumptions. Do not edit harness, meta-harness, gate thresholds, scenario definitions, or quality "
            "gates unless the current task brief explicitly allows those files and the failure evidence proves the "
            "evaluator itself is wrong."
        )
    if cls in ("receipt_gate", "scope_diff", "write_task_gate", "epic_alignment", "memory_gate", "programmatic_selftest"):
        return (
            "This is a harness control-plane failure. Repair only the named control-plane artifact when it is inside "
            "the current task scope; otherwise mark the task BLOCKED with the gate evidence."
        )
    return (
        "Repair only the current task's product changes unless the gate output names a specific harness control-plane "
        "file and that file is inside the task's allowed scope."
    )


def invoke_git_commit_all(message):
    global RepoRoot, DryRun
    changes = get_git_short_status()
    if not changes:
        write_runlog("INFO", f"no changes to commit for: {message}")
        return None
    if DryRun:
        write_runlog("INFO", f"[DRY RUN] skip git commit for: {message}")
        return None
    exclude_args = ["--", ".", ":(exclude).claude"]
    for prefix in (
        "cockpit-api/tmp",
        "harness-engine/.dev-harness/automation/auto_state.json",
        "harness-engine/.dev-harness/automation/program-state.json",
        "harness-engine/.dev-harness/automation/logs",
        "harness-engine/.dev-harness/memory/indexes",
        "harness-engine/meta-harness/evidence-packets/latest",
        "harness-engine/meta-harness/experience/latest",
        "harness-engine/meta-harness/replays/results/replay-*.json",
        "harness-engine/meta-harness/reports/contract-replay-*.md",
        "harness-engine/meta-harness/reports/meta-review-*.md",
        "harness-engine/meta-harness/semantic-reviews/latest",
        "harness-engine/meta-harness/signals/latest",
        "openclacky",
    ):
        exclude_args.append(f":(exclude){prefix}")
    subprocess.run(
        ["git", "add", "-A"] + exclude_args,
        cwd=RepoRoot, capture_output=True, text=True, encoding="utf-8"
    )
    diff_result = subprocess.run(
        ["git", "diff", "--cached", "--quiet"],
        cwd=RepoRoot, capture_output=True, text=True, encoding="utf-8"
    )
    if diff_result.returncode == 0:
        write_runlog("INFO", f"no staged changes to commit for: {message}")
        return None
    commit_result = invoke_git_captured("commit", "-m", message)
    for line in commit_result.get("output", []):
        write_runlog("INFO", line)
    if commit_result["exit_code"] != 0:
        commit_text = "\n".join(commit_result.get("output", []))
        if re.search(r"nothing to commit|no changes added to commit|working tree clean", commit_text):
            write_runlog("INFO", f"git commit found no committable changes for: {message}")
            return None
        raise RuntimeError(f"[auto-harness] git commit failed: {message}")
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=RepoRoot, capture_output=True, text=True, encoding="utf-8"
    )
    return result.stdout.strip()


PREFLIGHT_SAFE_COMMIT_PREFIXES = (
    "harness-engine/.dev-harness/scripts/",
    "harness-engine/.dev-harness/checks/",
    "harness-engine/.dev-harness/templates/",
    "harness-engine/.dev-harness/prompts/",
    "harness-engine/.dev-harness/automation/epics/",
    "harness-engine/.dev-harness/automation/auto_state.json",
    "harness-engine/.dev-harness/automation/program-state.json",
    "harness-engine/.dev-harness/memory/",
)


def preflight_auto_commit_safe_changes():
    """Auto-commit harness-safe file changes before entering the gate loop.

    Prevents the preflight AI repair loop from being triggered by intentional
    harness modifications (script edits, config updates, design doc copies).
    Only commits files whose paths match known safe prefixes.
    Returns True if any files were committed.
    """
    global RepoRoot, DryRun
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=RepoRoot, capture_output=True, text=True, encoding="utf-8"
    )
    if status.returncode != 0:
        return False
    safe_files = []
    for line in status.stdout.splitlines():
        if not line.strip():
            continue
        # Extract path (strip XY status and optional quote marks)
        parts = line.strip().split(None, 1)
        if len(parts) < 2:
            continue
        fpath = parts[1].strip('"')
        if is_local_workspace_path(fpath):
            continue
        if any(fpath.startswith(p) for p in PREFLIGHT_SAFE_COMMIT_PREFIXES):
            safe_files.append(fpath)
    if not safe_files:
        return False
    write_runlog("INFO", f"preflight auto-committing {len(safe_files)} safe harness file(s)")
    if DryRun:
        write_runlog("INFO", "[DRY RUN] skip preflight auto-commit safe harness changes")
        return False
    for f in safe_files:
        subprocess.run(["git", "add", f], cwd=RepoRoot, capture_output=True, text=True)
    r = subprocess.run(
        ["git", "commit", "-m", "auto-harness: preflight auto-commit safe harness changes"],
        cwd=RepoRoot, capture_output=True, text=True, encoding="utf-8"
    )
    if r.returncode == 0:
        short = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=RepoRoot, capture_output=True, text=True, encoding="utf-8"
        ).stdout.strip()
        write_runlog("INFO", f"preflight auto-commit {short}")
    return bool(safe_files)


def invoke_preflight(config, state, attempts, skip_preflight_ai=False, preflight_only=False):
    global RepoRoot, RunLogDir
    preflight_auto_commit_safe_changes()
    dirty = get_git_short_status()
    if not dirty:
        state["preflight"]["status"] = "CLEAN"
        state["last_error"] = None
        return True

    preflight_dir = RunLogDir
    ensure_dir(Path(preflight_dir))
    state["preflight"]["status"] = "RUNNING"
    state["preflight"]["log_dir"] = preflight_dir
    write_json_file(StatePath, state)

    for attempt in range(attempts + 1):
        gate = invoke_command_string(
            config["defaults"]["light_gate_command"],
            round_dir=preflight_dir,
            label=f"preflight light-gate attempt={attempt}"
        )
        state["preflight"]["gate_result"] = {"ok": gate["ok"], "exit_code": gate["exit_code"], "attempt": attempt}
        write_json_file(StatePath, state)
        if gate["ok"]:
            write_runlog("INFO", "preflight light gate passed; AI preflight role not needed")
            commit = None
            if not preflight_only:
                commit = invoke_git_commit_all("auto-harness: preflight preserve existing workspace changes")
            state["preflight"]["status"] = "DONE"
            state["preflight"]["commit"] = commit
            state["last_error"] = None
            write_json_file(StatePath, state)
            return True
        if test_preflight_gate_can_continue(gate):
            state["preflight"]["status"] = "CONTINUE_NEEDS_REVIEW"
            state["preflight"]["commit"] = None
            state["last_error"] = None
            write_json_file(StatePath, state)
            return True
        if attempt < attempts and not skip_preflight_ai:
            status_text = "\n".join(get_git_short_status())
            tracked_names = get_git_diff_names()
            staged_names = get_git_diff_names("--cached")
            tracked_text = "\n".join(tracked_names) if tracked_names else "(none)"
            staged_text = "\n".join(staged_names) if staged_names else "(none)"
            prompt = (
                "You are the repo preflight agent.\n"
                "Goal: make the current dirty workspace safe for the automation loop.\n\n"
                "You may repair existing uncommitted changes, but you must obey:\n"
                "- do not delete user work;\n"
                "- do not write real secrets;\n"
                "- do not edit files outside this repository;\n"
                "- inspect only tracked files and staged/unstaged git diffs outside `.claude/`;\n"
                "- do not read, diff, repair, stage, or commit any `.claude/` path;\n"
                "- treat `.claude/` as local runtime state excluded from automation scope;\n"
                "- do not read or quote ignored local runtime config such as `harness-engine/.dev-harness/automation/agent-config.json`;\n"
                "- environment variable names such as `OPENAI_API_KEY` or `ANTHROPIC_AUTH_TOKEN` are not secrets by themselves;\n"
                "- if you find merge conflicts, large dangerous deletions, secret exposure, or unclear cross-project changes, stop and write BLOCKED_PRECHECK.\n\n"
                f"Current git status:\n{status_text}\n\n"
                f"Tracked unstaged diff files:\n{tracked_text}\n\n"
                f"Staged diff files:\n{staged_text}\n\n"
                "Please repair the current changes, then run the light gate. If you cannot handle them safely, output BLOCKED_PRECHECK."
            )
            try:
                agent = invoke_agent_role(
                    config, "preflight", prompt, preflight_dir,
                    call_kind=f"attempt-{attempt + 1}",
                    enable_role_health_check=False
                )
                if preflight_output_reports_blocked_precheck(agent.get("output_text", "")):
                    state["last_error"] = "preflight role reported BLOCKED_PRECHECK"
                    state["preflight"]["status"] = "BLOCKED_PRECHECK"
                    state["status"] = "BLOCKED_PRECHECK"
                    write_json_file(StatePath, state)
                    invoke_git_commit_all("auto-harness: preflight BLOCKED_PRECHECK")
                    return False
                if not agent["ok"]:
                    state["last_error"] = "preflight role failed"
            except Exception as e:
                state["last_error"] = f"preflight role exception: {e}"

    state["preflight"]["status"] = "BLOCKED_PRECHECK"
    state["status"] = "BLOCKED_PRECHECK"
    write_json_file(StatePath, state)
    invoke_git_commit_all("auto-harness: preflight BLOCKED_PRECHECK")
    return False


def ensure_auto_branch(requested_branch, config):
    global RepoRoot, DryRun, RunStamp
    current = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=RepoRoot, capture_output=True, text=True, encoding="utf-8"
    ).stdout.strip()
    if DryRun:
        write_runlog("INFO", f"[DRY RUN] stay on current branch: {current}")
        return current
    if requested_branch:
        branch = requested_branch
    else:
        prefix = config.get("defaults", {}).get("branch_prefix", "codex/auto-harness")
        branch = f"{prefix}-{RunStamp}"

    if current == branch:
        return branch
    exists = subprocess.run(
        ["git", "branch", "--list", branch],
        cwd=RepoRoot, capture_output=True, text=True, encoding="utf-8"
    )
    if exists.stdout.strip():
        subprocess.run(["git", "switch", branch], cwd=RepoRoot, capture_output=True, text=True, encoding="utf-8")
    else:
        subprocess.run(["git", "switch", "-c", branch], cwd=RepoRoot, capture_output=True, text=True, encoding="utf-8")
    return branch


def build_writer_prompt(state, round_num, last_status, epic):
    epic_block = ""
    resume_hint = get_research_resume_hint()
    epic_status_line = ""
    if epic.get("enabled"):
        acceptance_items = ""
        contract = epic.get("contract", {})
        if contract and contract.get("acceptance_items"):
            acceptance_items = "\n".join(
                f"- {item.get('id')}: {item.get('description')} [{item.get('status')}]"
                for item in contract["acceptance_items"]
            )
        design_docs_guide = ""
        design_doc_files = epic.get("design_doc_files", [])
        if design_doc_files:
            doc_list = "\n".join(f"  - {d['path']}" for d in design_doc_files)
            design_docs_guide = (
                "\nMANDATORY: Before generating the task brief, read the full design documents.\n"
                "These contain authoritative specifications (data models, API contracts, permission rules).\n"
                f"Read each of these files in full:\n{doc_list}\n"
                "Do NOT skip reading these docs. The design.md summary above only lists references.\n"
            )
        epic_block = (
            f"\nProgram/Epic context:\n"
            f"- Epic ID: {epic.get('id')}\n"
            f"- Epic complete: {epic.get('complete')}\n"
            f"- Contract path: {epic.get('contract_path')}\n"
            f"- Goal path: {epic.get('goal_path')}\n"
            f"- Design path: {epic.get('design_path')}\n"
            f"- Backlog path: {epic.get('backlog_path')}\n\n"
            f"- Structured backlog path: {epic.get('backlog_json_path') or 'none'}\n"
            f"- Rolling planner spec path: {epic.get('planner_spec_path') or 'not prepared'}\n\n"
            f"Epic acceptance items:\n{acceptance_items}\n\n"
            f"Goal document:\n{epic.get('goal_text')}\n\n"
            f"Design document:\n{epic.get('design_text')}\n\n"
            f"{design_docs_guide}\n"
            f"Backlog document:\n{epic.get('backlog_text')}\n\n"
            "Mandatory alignment rules:\n"
            "- Choose exactly one pending acceptance item from the epic contract.\n"
            "- The task brief must include an `## Epic Alignment` section.\n"
            "- It must include `Epic ID`, `Acceptance Item`, `Design Section`, and `Goal Reference`.\n"
            "- Do not write work outside the epic goal/design/contract.\n"
        )
        if epic.get("planner_spec_path"):
            epic_block += (
                "\nRolling planner rule:\n"
                "- This SpecFile was prepared by `harness-engine/.dev-harness/scripts/rolling_task_planner.py` from the active contract and structured backlog.\n"
                "- Prefer the prepared rolling task spec over free-form task selection.\n"
                f"- Run `python harness-engine/.dev-harness/scripts/new_task_brief.py --SpecFile {epic.get('planner_spec_path')}`.\n"
                "- Only depart from the prepared spec for a bounded repair named by the latest gate evidence.\n"
            )
        elif epic.get("backlog_json_path"):
            epic_block += (
                "\nRolling planner rule:\n"
                "- Before selecting work manually, run `harness-engine/.dev-harness/scripts/rolling_task_planner.py` with the active contract and backlog.json to prepare a SpecFile.\n"
            )
        if epic.get("complete"):
            epic_status_line = "- The current epic contract is complete; do not generate another task for this completed epic unless an explicit TaskBriefPath was supplied."

    return (
        "You are the Codex/GPT architect.\n"
        "Create or update the next scoped task brief according to the repo harness rules.\n\n"
        f"Automation context:\n"
        f"- round: {round_num} / {state.get('max_iterations')}\n"
        f"- previous result: {last_status}\n"
        f"{epic_status_line}\n"
        "- If the previous round failed only because of local `.claude` settings or\n"
        "  `.claude/worktrees/agent-*`, do not generate another structure-proof repair.\n"
        "  Treat it as an external workspace blocker outside the research stream.\n"
        "- If the previous round failed for product/research work inside scope, write one\n"
        "  bounded repair. Otherwise resume the research roadmap below.\n"
        "- The task brief must keep Task Status: UNCLAIMED.\n"
        "- It must include Task Stream, Previous Task Acceptance, Allowed/Forbidden scope,\n"
        "  acceptance criteria, verification commands, and Stop Conditions.\n"
        "- First run or inspect `harness-engine/.dev-harness/scripts/harness_context_summary.py`.\n"
        "- Resolve repo root before shell commands. Run harness scripts/checks from\n"
        "  repo root or repo-root absolute paths; never run harness generators from\n"
        "  inside cockpit-api.\n"
        "- Before reading a guessed/generated path, verify file exists before Read\n"
        "  with a bounded listing or Test-Path equivalent.\n"
        "- Canonical task queue directories are `harness-engine/.dev-harness/task-briefs/`,\n"
        "  `harness-engine/.dev-harness/execution-receipts/`, and\n"
        "  `harness-engine/.dev-harness/reviews/`. Do not guess task or receipt paths\n"
        "  under `harness-engine/.dev-harness/automation/`; automation is state/logs only.\n"
        "- Prefer an explicit TaskBriefPath from automation state over path guesses.\n"
        "- If `cd cockpit-api` fails once, stop and resolve repo root; do not retry\n"
        "  relative cd commands.\n"
        "- Do not Glob/Grep/Read all files under `task-briefs/`, `reviews/`,\n"
        "  `execution-receipts/`, or `harness-engine/.dev-harness/**/*.md`.\n"
        "- Read only the latest relevant task, its same-number receipt/review, and at\n"
        "  most the latest same-stream predecessor unless a gate failure names more.\n"
        "- Create the task with `harness-engine/.dev-harness/scripts/new_task_brief.py`.\n"
        "  Do not hand-write a whole task brief unless the generator cannot express the\n"
        "  task; if so, state the exact missing generator capability in the brief.\n"
        "- When calling `new_task_brief.py` with list parameters, repeat the named\n"
        "  option for each list item and do not pass bare positional list values.\n"
        "  List fields include: StopConditions, AcceptanceCriteria, NonGoals,\n"
        "  AllowedPaths, ForbiddenPaths, AllowedOperations, ForbiddenOperations,\n"
        "  VerificationCommands. Format: --StopConditions 'cond1' --StopConditions 'cond2'.\n"
        "  If you get 'spec field must be a list' error, switch to --SpecFile.\n"
        "- Do not encode long JSON or many repeated list options in a shell command.\n"
        "  For long task input, use a Write/edit tool to create a bounded JSON spec,\n"
        "  call `new_task_brief.py --SpecFile <path>`, then remove any temporary spec.\n"
        "  The spec must include Title, TaskStream, RunType, Layer, RiskClass, Intent,\n"
        "  and Goal before invoking the generator; do not call it with partial specs.\n"
        "- For review drafts, prefer `new_review_draft.py --Task <NNN>` over\n"
        "  writing a full review by hand.\n"
        f"{resume_hint}\n"
        f"{epic_block}\n\n"
        "Only write or update the task brief. Do not execute the task."
    )


def build_implementer_prompt(round_num, task_brief, task_status="UNCLAIMED", epic=None):
    if task_status == "CLAIMED":
        status_instruction = "It is already CLAIMED from a previous interrupted run. Continue this same task; do not create or claim another task."
    else:
        status_instruction = "It must have Task Status: UNCLAIMED. Claim this same task before executing."
    design_docs_guide = ""
    if epic and epic.get("enabled"):
        design_doc_files = epic.get("design_doc_files", [])
        if design_doc_files:
            doc_list = "\n".join(f"  - {d['path']}" for d in design_doc_files)
            design_docs_guide = (
                "\nDesign documents: read the authoritative specs before implementing.\n"
                f"Read each file in full:\n{doc_list}\n"
                "These contain data models, API contracts, and permission rules.\n\n"
            )
    return (
        "You are the bounded implementer.\n"
        "Execute only this task brief:\n\n"
        f"{task_brief}\n\n"
        f"{status_instruction} Do not execute any other task brief, even if another older\n"
        "UNCLAIMED or CLAIMED task exists.\n\n"
        f"{design_docs_guide}"
        "Requirements:\n"
        "- if UNCLAIMED, claim the task and change status to CLAIMED;\n"
        "- only edit files inside the allowed scope;\n"
        "- use `harness-engine/.dev-harness/scripts/harness_context_summary.py` for\n"
        "  orientation instead of scanning all harness markdown;\n"
        "- resolve repo root before shell commands; run harness scripts/checks from\n"
        "  repo root or repo-root absolute paths, never from inside cockpit-api;\n"
        "- before reading a guessed/generated path, verify file exists before Read\n"
        "  with a bounded listing or Test-Path equivalent;\n"
        "- canonical task queue directories are `harness-engine/.dev-harness/task-briefs/`,\n"
        "  `harness-engine/.dev-harness/execution-receipts/`, and\n"
        "  `harness-engine/.dev-harness/reviews/`; do not guess task or receipt paths\n"
        "  under `harness-engine/.dev-harness/automation/`, which is state/logs only;\n"
        "- prefer an explicit TaskBriefPath from automation state over path guesses;\n"
        "- if `cd cockpit-api` fails once, stop and resolve repo root instead of\n"
        "  retrying relative cd commands;\n"
        "- if asked to create/repair a task brief or review draft, use the generator\n"
        "  scripts instead of writing the full skeleton by hand;\n"
        "- **DELIVERABLE COMPLETENESS CHECK (MANDATORY)**: before marking DONE, verify\n"
        "  every file listed in `Files Expected` actually exists and is non-empty.\n"
        "  Use `ls -la` or equivalent; do NOT assume files were created. If any\n"
        "  expected file is missing, fix it first or mark BLOCKED. This is the\n"
        "  direct lesson from task-001 FAIL where 7 core files were missing.\n"
        "- finish by changing the status to DONE or BLOCKED;\n"
        "- return or write a receipt using\n"
        "  `harness-engine/.dev-harness/templates/execution-receipt-template.md`;\n"
        "- if marking BLOCKED, the receipt must include an evaluator/checker repair\n"
        "  proposal that would catch this blocker earlier in a future task;\n"
        "- verify your own changes: run relevant tests, linters, and gate checks before\n"
        "  marking DONE; if any verification fails, fix the issue or mark BLOCKED;\n"
        "- if you need to exceed scope, touch forbidden files, cannot verify, or the task\n"
        "  is incomplete, stop and mark BLOCKED.\n\n"
        f"Current automation round: {round_num}."
    )


def build_implementer_repair_prompt(round_num, gate):
    cls = get_gate_failure_class(gate)
    excerpt = get_gate_output_excerpt(str(gate.get("output", "")))
    guidance = get_gate_repair_guidance(cls)
    return (
        f"Current round {round_num} failed verification.\n"
        f"Failure class: {cls}.\n\n"
        f"{guidance}\n\n"
        "Repair only if this failure is inside the current task brief's allowed scope.\n"
        "Do not create another task, do not change review artifacts, and do not broaden\n"
        "scope. If the task is already BLOCKED or the failure is outside scope, only\n"
        "ensure the receipt/task status says BLOCKED with exact evidence, then stop.\n\n"
        f"Failure output excerpt:\n{excerpt}\n\n"
        "After the repair, stop and let the harness rerun the gate."
    )


def main():
    global WorkerId, RepoRoot, AutomationRoot, LogRoot, RunStamp, RunLogDir, RunConsoleLog, LatestFile
    global DryRun, StatePath, ProgramStatePath, AgentDisplayEmitHost, ResumeTaskBriefPath

    parser = argparse.ArgumentParser(description="auto harness loop")
    parser.add_argument("--MaxIterations", type=int, default=0)
    parser.add_argument("--ConfigPath", default="harness-engine/.dev-harness/automation/agent-config.json")
    parser.add_argument("--StatePath", default="harness-engine/.dev-harness/automation/auto_state.json")
    parser.add_argument("--ProgramStatePath", default="harness-engine/.dev-harness/automation/program-state.json")
    parser.add_argument("--EpicId", default="")
    parser.add_argument("--EpicRoot", default="")
    parser.add_argument("--EpicContractPath", default="")
    parser.add_argument("--GoalPath", default="")
    parser.add_argument("--DesignPath", default="")
    parser.add_argument("--BacklogPath", default="")
    parser.add_argument("--BranchName", default="")
    parser.add_argument("--WorkerId", default="")
    parser.add_argument("--FullGateEvery", type=int, default=0)
    parser.add_argument("--MaxFixAttempts", type=int, default=-1)
    parser.add_argument("--PreflightFixAttempts", type=int, default=-1)
    parser.add_argument("--TaskBriefPath", default="")
    parser.add_argument("--AutoPush", action="store_true")
    parser.add_argument("--SkipPreflightAi", action="store_true")
    parser.add_argument("--EnableRoleHealthCheck", action="store_true")
    parser.add_argument("--LightGateOnly", action="store_true")
    parser.add_argument("--PreflightOnly", action="store_true")
    parser.add_argument("--LogRootOverride", default="")
    parser.add_argument("--DryRun", action="store_true")
    args = parser.parse_args()

    max_iterations = args.MaxIterations
    config_path = args.ConfigPath
    StatePath = args.StatePath
    ProgramStatePath = args.ProgramStatePath
    epic_id = args.EpicId
    epic_root = args.EpicRoot
    epic_contract_path = args.EpicContractPath
    goal_path = args.GoalPath
    design_path = args.DesignPath
    backlog_path = args.BacklogPath
    branch_name = args.BranchName
    WorkerId = args.WorkerId
    full_gate_every = args.FullGateEvery
    max_fix_attempts = args.MaxFixAttempts
    preflight_fix_attempts = args.PreflightFixAttempts
    task_brief_path_arg = args.TaskBriefPath
    auto_push = args.AutoPush
    skip_preflight_ai = args.SkipPreflightAi
    enable_role_health_check = args.EnableRoleHealthCheck
    light_gate_only = args.LightGateOnly
    preflight_only = args.PreflightOnly
    log_root_override = args.LogRootOverride
    DryRun = args.DryRun

    if not WorkerId:
        WorkerId = f"W{os.getpid()}"

    # Find repo root
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode != 0 or not result.stdout.strip():
        print("[auto-harness] not inside a git repository", file=sys.stderr)
        sys.exit(1)
    RepoRoot = str(Path(result.stdout.strip()).resolve())
    os.chdir(RepoRoot)

    AutomationRoot = os.path.join(RepoRoot, "harness-engine", ".dev-harness", "automation")
    os.makedirs(AutomationRoot, exist_ok=True)
    if log_root_override:
        LogRoot = log_root_override
    else:
        LogRoot = os.path.join(AutomationRoot, "logs")
    os.makedirs(LogRoot, exist_ok=True)

    RunStamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    RunLogDir = os.path.join(LogRoot, f"run-{RunStamp}-{WorkerId}")
    os.makedirs(RunLogDir, exist_ok=True)
    RunConsoleLog = os.path.join(RunLogDir, "console.log")
    LatestFile = os.path.join(RunLogDir, "latest.txt")
    AgentDisplayEmitHost = True
    ResumeTaskBriefPath = None
    Path(RunConsoleLog).write_text("", encoding="utf-8")

    # Load config
    if not Path(config_path).exists():
        example = "harness-engine/.dev-harness/automation/agent-config.example.json"
        if Path(example).exists():
            import shutil
            shutil.copy2(example, config_path)
            write_runlog("WARN", f"created config from example: {config_path}")
        else:
            raise RuntimeError(f"[auto-harness] missing config: {config_path}")

    config = read_json_file(config_path)
    if not config:
        raise RuntimeError(f"[auto-harness] could not read config: {config_path}")

    epic = resolve_epic_context(epic_id, epic_root, epic_contract_path, goal_path, design_path, backlog_path)

    if max_iterations <= 0:
        max_iterations = int(config.get("defaults", {}).get("max_iterations", 0))
    if max_iterations <= 0:
        max_iterations = 1
    if full_gate_every <= 0:
        full_gate_every = int(config.get("defaults", {}).get("full_gate_every", 0))
    if full_gate_every <= 0:
        full_gate_every = 5
    if max_fix_attempts < 0:
        max_fix_attempts = int(config.get("defaults", {}).get("max_fix_attempts", -1))
    if max_fix_attempts < 0:
        max_fix_attempts = 2
    if preflight_fix_attempts < 0:
        preflight_fix_attempts = int(config.get("defaults", {}).get("preflight_fix_attempts", -1))
    if preflight_fix_attempts < 0:
        preflight_fix_attempts = 2

    resolved_task_brief_path = resolve_task_brief_path(task_brief_path_arg) if task_brief_path_arg else None

    effective_auto_push = bool(config.get("defaults", {}).get("auto_push", False)) or auto_push
    config["roles"] = {
        "task_writer": config.get("roles", {}).get("task_writer", {}),
        "implementer": config.get("roles", {}).get("implementer", {}),
        "preflight": config.get("roles", {}).get("preflight", {}),
    }

    if Path(StatePath).exists():
        state = read_json_file(StatePath)
    else:
        state = new_auto_state(max_iterations, branch_name, effective_auto_push, full_gate_every)
    state["max_iterations"] = max_iterations
    state["full_gate_every"] = full_gate_every
    state["auto_push"] = effective_auto_push
    state["worker_id"] = WorkerId
    state["status"] = "RUNNING"
    write_json_file(StatePath, state)
    write_run_summary(state, "RUNNING")

    write_runlog("INFO", f"auto harness loop starting max={max_iterations} full_every={full_gate_every}")

    completed_epic_guard = guard_completed_epic_before_preflight(epic, state, resolved_task_brief_path)
    epic = completed_epic_guard.get("epic", epic)
    if completed_epic_guard.get("handled"):
        sys.exit(0)

    if epic.get("enabled") and not resolved_task_brief_path:
        epic["planner_spec_path"] = prepare_rolling_task_spec(epic)

    if not invoke_preflight(config, state, preflight_fix_attempts, skip_preflight_ai, preflight_only):
        write_runlog("ERROR", "preflight blocked")
        sys.exit(2)
    if preflight_only:
        write_run_summary(state, "PREFLIGHT_ONLY_DONE")
        write_runlog("INFO", "preflight-only finished")
        sys.exit(0)

    if test_repair_spiral_risk() and not resolved_task_brief_path and (not epic.get("enabled") or epic.get("complete")):
        write_runlog("WARN", "repair spiral risk detected before task_writer; refusing automatic repair-task generation")
        hint = get_research_resume_hint().replace("\r\n", " | ").replace("\n", " | ")
        write_runlog("INFO", hint)
        state["status"] = "REPAIR_SPIRAL_NEEDS_RESEARCH_RESET"
        state["last_result"] = "REPAIR_SPIRAL_GUARD"
        state["last_error"] = "recent task briefs are repair-heavy; require explicit task or active research epic"
        write_json_file(StatePath, state)
        write_run_summary(state, state["status"])
        sys.exit(0)

    branch = ensure_auto_branch(branch_name, config)
    state["branch"] = branch
    write_json_file(StatePath, state)
    write_run_summary(state, "RUNNING")

    for round_num in range(1, max_iterations + 1):
        round_dir = os.path.join(RunLogDir, f"round-{round_num:03d}")
        os.makedirs(round_dir, exist_ok=True)
        state["current_round"] = round_num
        write_json_file(StatePath, state)

        write_runlog("INFO", f"round {round_num} start")
        round_result = {
            "round": round_num,
            "status": "RUNNING",
            "log_dir": round_dir,
            "task_brief": None,
            "receipt": None,
            "writer_role": None,
            "implementer_role": None,
            "resume_mode": None,
            "gate": None,
            "commit": None,
            "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "completed_at": None,
        }

        pre_writer_latest_task = get_latest_task_brief()
        pre_writer_latest_status = get_task_status(pre_writer_latest_task)
        resume_target_task = ResumeTaskBriefPath if ResumeTaskBriefPath else pre_writer_latest_task
        if not ResumeTaskBriefPath and resume_target_task and not test_task_matches_epic(resume_target_task, epic):
            # latest task does not match active epic
            write_runlog("INFO", f"latest task does not match active epic; task_writer will create the next aligned task: {resume_target_task}")
            resume_target_task = None
        resume_target_status = get_task_status(resume_target_task)
        last_status = state.get("last_result", "none") or "none"

        if resolved_task_brief_path:
            write_runlog("INFO", f"round {round_num} using explicit task brief: {resolved_task_brief_path}")
            writer = {"ok": True, "role": "explicit_task", "exit_code": 0}
            round_result["writer_role"] = "explicit_task"
            round_result["task_brief"] = resolved_task_brief_path
        elif resume_target_task and resume_target_status in ("UNCLAIMED", "CLAIMED"):
            write_runlog("INFO", f"round {round_num} resuming {resume_target_status} task without task_writer: {resume_target_task}")
            writer = {"ok": True, "role": "resume_existing_task", "exit_code": 0}
            round_result["writer_role"] = "resume_existing_task"
            round_result["task_brief"] = resume_target_task
        elif epic.get("planner_spec_path"):
            write_runlog("INFO", f"round {round_num} using rolling planner SpecFile: {epic.get('planner_spec_path')}")
            writer = invoke_programmatic_task_writer(epic["planner_spec_path"], round_dir)
            round_result["writer_role"] = writer["role"]
            round_result["task_brief"] = get_latest_task_brief()
        else:
            writer = invoke_agent_role(
                config, "task_writer",
                build_writer_prompt(state, round_num, last_status, epic),
                round_dir, call_kind="main",
                enable_role_health_check=enable_role_health_check,
            )
            round_result["writer_role"] = writer["role"]
            round_result["task_brief"] = get_latest_task_brief()
            if epic.get("enabled") and not test_task_matches_epic(round_result["task_brief"], epic):
                write_runlog("WARN", f"task_writer did not create an active-epic task for {epic.get('id')}: {round_result['task_brief']}")
                round_result["task_brief"] = None
                # TASK_WRITER_MISSING_EPIC_ALIGNED_TASK
                round_result["resume_mode"] = "TASK_WRITER_MISSING_EPIC_ALIGNED_TASK"
                writer["ok"] = False

        state["last_task_brief"] = round_result["task_brief"]
        write_json_file(StatePath, state)
        write_round_summary(round_dir, round_result)
        write_run_summary(state, "RUNNING")

        task_status = get_task_status(round_result["task_brief"])
        task_was_not_created = (not resolved_task_brief_path and round_result["task_brief"] == pre_writer_latest_task)
        if task_was_not_created and task_status == "UNCLAIMED":
            write_runlog("INFO", f"task_writer reused existing latest UNCLAIMED task: {round_result['task_brief']}")
        if test_auto_external_workspace_repair_rejected(round_result["task_brief"], task_status, bool(resolved_task_brief_path)):
            write_runlog("WARN", f"rejecting automatic external-workspace repair task before implementer: {round_result['task_brief']}")
            hint = get_research_resume_hint().replace("\r\n", " | ").replace("\n", " | ")
            write_runlog("INFO", hint)
            round_result["resume_mode"] = "REJECTED_EXTERNAL_WORKSPACE_REPAIR"
            round_result["status"] = "REJECTED_EXTERNAL_WORKSPACE_REPAIR"
            round_result["gate"] = {"command": "auto-task-policy", "ok": False, "exit_code": 1, "full": False}
            round_result["completed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            state["last_result"] = "REJECTED_EXTERNAL_WORKSPACE_REPAIR"
            state["last_error"] = "automatic .claude/external-workspace repair tasks must be explicit and outside the research stream"
            state["rounds"] = state.get("rounds", []) + [round_result]
            write_json_file(StatePath, state)
            write_round_summary(round_dir, round_result, round_result["gate"])
            write_run_summary(state, round_result["status"])
            break

        if task_status == "UNCLAIMED":
            round_result["resume_mode"] = "IMPLEMENT"
        elif task_status == "CLAIMED":
            round_result["resume_mode"] = "CONTINUE_IMPLEMENT"
        elif task_status in ("DONE", "BLOCKED"):
            round_result["resume_mode"] = "NEXT_TASK"
        else:
            round_result["resume_mode"] = "INVALID"
        write_runlog("INFO", f"round {round_num} task status={task_status} resume_mode={round_result['resume_mode']}")

        if round_result["resume_mode"] == "NEXT_TASK" and not resolved_task_brief_path and round_result["writer_role"] not in ("task_writer",):
            writer = invoke_agent_role(
                config, "task_writer",
                build_writer_prompt(state, round_num, last_status, epic),
                round_dir, call_kind="main",
                enable_role_health_check=enable_role_health_check,
            )
            round_result["writer_role"] = writer["role"]
            round_result["task_brief"] = get_latest_task_brief()
            if epic.get("enabled") and not test_task_matches_epic(round_result["task_brief"], epic):
                write_runlog("WARN", f"task_writer did not create an active-epic task for {epic.get('id')}: {round_result['task_brief']}")
                round_result["task_brief"] = None
                round_result["resume_mode"] = "TASK_WRITER_MISSING_EPIC_ALIGNED_TASK"
                writer["ok"] = False
            state["last_task_brief"] = round_result["task_brief"]
            task_status = get_task_status(round_result["task_brief"])
            if test_auto_external_workspace_repair_rejected(round_result["task_brief"], task_status, bool(resolved_task_brief_path)):
                write_runlog("WARN", f"rejecting task_writer external-workspace repair task before implementer: {round_result['task_brief']}")
                hint = get_research_resume_hint().replace("\r\n", " | ").replace("\n", " | ")
                write_runlog("INFO", hint)
                round_result["resume_mode"] = "REJECTED_EXTERNAL_WORKSPACE_REPAIR"
                round_result["status"] = "REJECTED_EXTERNAL_WORKSPACE_REPAIR"
                round_result["gate"] = {"command": "auto-task-policy", "ok": False, "exit_code": 1, "full": False}
                round_result["completed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
                state["last_result"] = "REJECTED_EXTERNAL_WORKSPACE_REPAIR"
                state["last_error"] = "task_writer generated .claude/external-workspace repair; require explicit task or active research epic"
                state["rounds"] = state.get("rounds", []) + [round_result]
                write_json_file(StatePath, state)
                write_round_summary(round_dir, round_result, round_result["gate"])
                write_run_summary(state, round_result["status"])
                break
            if task_status == "UNCLAIMED":
                round_result["resume_mode"] = "IMPLEMENT"
            elif task_status == "CLAIMED":
                round_result["resume_mode"] = "CONTINUE_IMPLEMENT"
            else:
                round_result["resume_mode"] = "INVALID"
            write_json_file(StatePath, state)
            write_runlog("INFO", f"round {round_num} task_writer selected task status={task_status} resume_mode={round_result['resume_mode']}: {round_result['task_brief']}")

        if (not writer.get("ok") or not round_result["task_brief"] or
                round_result["resume_mode"] == "INVALID" or
                (resolved_task_brief_path and task_status not in ("UNCLAIMED", "CLAIMED", "DONE", "BLOCKED"))):
            round_result["status"] = "FAILED"
            round_result["gate"] = {"command": "not run", "ok": False, "exit_code": 1, "full": False}
            round_result["completed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            state["last_result"] = "FAILED"
            if resolved_task_brief_path:
                state["last_error"] = "explicit task brief is not resumable"
            else:
                state["last_error"] = "task writer did not provide a resumable task for this round"
            state["rounds"] = state.get("rounds", []) + [round_result]
            write_json_file(StatePath, state)
            write_round_summary(round_dir, round_result, round_result["gate"])
            write_run_summary(state, "RUNNING")
            commit = invoke_git_commit_all(f"auto-harness: round {round_num:03d} FAILED task-writer")
            round_result["commit"] = commit
            state["last_commit"] = commit
            write_json_file(StatePath, state)
            if should_stop_after_writer_failure(writer, resolved_task_brief_path):
                state["status"] = "STOPPED_AFTER_TASK_WRITER_FAILURE"
                state["last_result"] = "STOPPED_AFTER_TASK_WRITER_FAILURE"
                state["last_error"] = "task_writer failed; stop before reusing a partial generated task"
                write_json_file(StatePath, state)
                write_run_summary(state, state["status"])
                write_runlog("ERROR", state["last_error"])
                break
            continue

        if epic.get("enabled") and epic.get("contract_path"):
            alignment_gate = invoke_command_string(
                build_epic_alignment_gate_command(round_result["task_brief"], epic["contract_path"]),
                round_dir=round_dir,
                label="epic-alignment-gate"
            )
            if not alignment_gate["ok"]:
                round_result["status"] = "MISALIGNED_COMMITTED"
                round_result["gate"] = {"command": "epic-alignment-gate", "ok": False, "exit_code": alignment_gate["exit_code"], "full": False}
                round_result["completed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
                state["last_result"] = "MISALIGNED_COMMITTED"
                state["last_error"] = "task brief failed epic alignment gate"
                state["rounds"] = state.get("rounds", []) + [round_result]
                write_trace_summary(round_dir, epic, round_result, round_result["gate"])
                write_json_file(StatePath, state)
                write_round_summary(round_dir, round_result, round_result["gate"])
                write_run_summary(state, "RUNNING")
                commit = invoke_git_commit_all(f"auto-harness: round {round_num:03d} MISALIGNED_COMMITTED")
                round_result["commit"] = commit
                state["last_commit"] = commit
                write_json_file(StatePath, state)
                update_program_round_state(epic, state, round_result)
                continue

        is_full_gate = (not light_gate_only) and ((round_num % full_gate_every == 0) or (round_num == max_iterations))
        gate_command = config["defaults"]["full_gate_command"] if is_full_gate else config["defaults"]["light_gate_command"]
        implementer = invoke_agent_role(
            config, "implementer",
            build_implementer_prompt(round_num, round_result["task_brief"], task_status, epic),
            round_dir, call_kind="main",
            enable_role_health_check=enable_role_health_check,
        )
        round_result["implementer_role"] = implementer["role"]
        task_status = get_task_status(round_result["task_brief"])
        gate = invoke_command_string(gate_command, round_dir=round_dir, label="gate attempt=0")

        for fix in range(1, max_fix_attempts + 1):
            if gate["ok"]:
                break
            failure_class = get_gate_failure_class(gate)
            if not test_implementer_repair_worth_running(gate, task_status):
                write_runlog("INFO", f"skip implementer repair-{fix} failure_class={failure_class} task_status={task_status}")
                break
            repair_prompt = build_implementer_repair_prompt(round_num, gate)
            invoke_agent_role(
                config, "implementer", repair_prompt, round_dir,
                call_kind=f"repair-{fix}",
                enable_role_health_check=enable_role_health_check,
            )
            task_status = get_task_status(round_result["task_brief"])
            gate = invoke_command_string(gate_command, round_dir=round_dir, label=f"gate attempt={fix}")

        round_result["gate"] = {"command": gate_command, "ok": gate["ok"], "exit_code": gate["exit_code"], "full": is_full_gate}
        round_result["status"] = "DONE" if (gate["ok"] and implementer["ok"]) else "FAILED"
        round_result["completed_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        state["last_result"] = round_result["status"]
        state["rounds"] = state.get("rounds", []) + [round_result]
        write_json_file(StatePath, state)
        write_trace_summary(round_dir, epic, round_result, round_result["gate"])
        write_round_summary(round_dir, round_result, round_result["gate"])
        write_run_summary(state, "RUNNING")

        commit_message = f"auto-harness: round {round_num:03d} {round_result['status']}"
        commit = invoke_git_commit_all(commit_message)
        round_result["commit"] = commit
        state["last_commit"] = commit
        write_json_file(StatePath, state)
        update_program_round_state(epic, state, round_result)
        invoke_git_commit_all(f"auto-harness: round {round_num:03d} state")

        if effective_auto_push:
            push_result = subprocess.run(
                ["git", "push", "-u", "origin", branch],
                cwd=RepoRoot, capture_output=True, text=True, encoding="utf-8"
            )
            if push_result.returncode != 0:
                write_runlog("WARN", f"push failed for {branch}; continuing")

    state["status"] = "DONE"
    write_json_file(StatePath, state)
    invoke_git_commit_all("auto-harness: final state DONE")
    write_run_summary(state, "DONE")
    write_runlog("INFO", "auto harness loop finished")


if __name__ == "__main__":
    main()

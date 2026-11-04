"""`grokbot-kit login <tool>` pelo comando oficial de cada CLI (AC 92-94, doors 3, 7 e 20)."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from grokbot_kit import config


def _err(message: str) -> int:
    print(f"grokbot-kit login: {message}", file=sys.stderr)
    return 1


def login_argv(tool: str, method: str) -> list[str]:
    """Os argumentos do comando oficial de login; vazio quando não há comando a rodar (API key do Claude e do dsh)."""
    if tool == "codex":
        return ["login", "--with-api-key"] if method == "api-key" else ["login", "--device-auth"]
    if tool == "claude":
        return [] if method == "api-key" else ["auth", "login"]
    return ["auth", "login"]


def _dsh_env_write(path: Path, key: str) -> None:
    """Grava/atualiza `DEEPSEEK_API_KEY` no `.env` do dsh com modo `0600`, sem tocar nas outras linhas."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        lines = []
    kept = [line for line in lines if line.partition("=")[0].strip() != "DEEPSEEK_API_KEY"]
    tmp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write("\n".join([*kept, f"DEEPSEEK_API_KEY={key}"]) + "\n")
        os.replace(tmp, path)
    except OSError:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _login_dsh(cli: dict[str, Any], method: str, secret: str | None) -> int:
    """O dsh não tem login por assinatura: a API key vive no `.env` do `$DSH_HOME`, nunca no config ou no stdout."""
    if method != "api-key":
        return _err("dsh uses an API key only; run: grokbot-kit login dsh --method api-key")
    env_file = config.dsh_env_file(cli)
    if secret is None and config.dsh_api_key_present(cli):
        print(f"dsh: already configured (DEEPSEEK_API_KEY present in {env_file} or the environment)")
        return 0
    name = secret or "dsh-api-key"
    try:
        key = config.read_secret(name)
    except config.ConfigError as e:
        return _err(str(e))
    if not key:
        return _err(f"secret {name!r} is empty")
    try:
        _dsh_env_write(env_file, key)
    except OSError as e:
        return _err(f"cannot write {env_file}: {e.strerror}")
    print(f"dsh: logged in (api-key); DEEPSEEK_API_KEY written to {env_file} (mode 0600)")
    return 0


def login(tool: str, method: str, secret: str | None) -> int:
    try:
        cfg = config.load(validate=False) if config.config_path().exists() else {}
    except config.ConfigError as e:
        return _err(str(e))
    cli: dict[str, Any] = cfg.get("cli", {}).get(tool, {})
    if tool == "dsh":
        return _login_dsh(cli, method, secret)
    secret = secret or f"{tool}-api-key"
    argv = login_argv(tool, method)
    key = None
    if method == "api-key" and tool in ("codex", "claude"):
        try:
            key = config.read_secret(secret)
        except config.ConfigError as e:
            return _err(str(e))

    if tool == "claude":
        if method == "api-key":
            cli["api_key_secret"] = secret
        else:
            cli.pop("api_key_secret", None)
    if argv:
        env = {**os.environ, **config.cli_env(tool, {k: v for k, v in cli.items() if k != "api_key_secret"})}
        if tool == "codex":
            Path(env["CODEX_HOME"]).mkdir(parents=True, exist_ok=True, mode=0o700)
        bin_path = os.path.expanduser(str(cli.get("bin", tool)))
        stdin = None if key is None else (key + "\n")
        try:
            proc = subprocess.run([bin_path, *argv], input=stdin, text=True, env=env, check=False)
        except OSError as e:
            return _err(f"cannot run {bin_path}: {e.strerror}")
        if proc.returncode != 0:
            return _err(f"{tool} {' '.join(argv)} exited {proc.returncode}")
    if tool == "claude":
        cfg.setdefault("cli", {})["claude"] = cli
        config.save(cfg)
    print(f"{tool}: logged in ({method})")
    return 0

"""`grokbot-kit emit`: chamado pelos hooks dos agentes dentro de uma task (AC 54-63).

Antes do gate de `GROKBOT_KIT_TASK_ID` só entram `os`, `sys` e `json` (door 6); o resto é carregado sob demanda.
O emit nunca envia evento terminal (door 5): só `needs_input`, normalizado de cada fonte (door 14). Em qualquer
caso sai com `0` e escreve `{}` em stdout, porque o Codex exige JSON em alguns eventos; erros vão para o `kit.log`.
"""

import json
import os
import sys

SOURCES = ("opencode", "claude", "codex", "dsh")
_SAFE_ID = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._-")


def _hash(*parts: object) -> str:
    import hashlib

    canonical = json.dumps(parts, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _discriminator(request_id: object, tool_name: object, tool_input: object) -> str:
    if isinstance(request_id, str) and request_id and set(request_id) <= _SAFE_ID:
        return request_id
    if isinstance(request_id, str) and request_id:
        return _hash(request_id)
    return _hash(tool_name, tool_input)


def _str(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _detail(tool_input: object) -> str | None:
    if isinstance(tool_input, dict):
        for key in ("command", "file_path", "path"):
            if isinstance(tool_input.get(key), str):
                return str(tool_input[key])
    return json.dumps(tool_input, ensure_ascii=False) if tool_input is not None else None


def normalize(source: str, data: object) -> dict[str, str | None] | None:
    """O `needs_input` que o JSON do hook representa, ou `None` quando o hook não é um pedido ao usuário."""
    if not isinstance(data, dict):
        return None
    if source in ("claude", "codex"):
        if data.get("hook_event_name") != "PermissionRequest" or not _str(data.get("tool_name")):
            return None
        tool_input = data.get("tool_input")
        return {
            "kind": "permission",
            "tool_name": data["tool_name"],
            "detail": _detail(tool_input),
            "discriminator": _discriminator(data.get("tool_use_id"), data["tool_name"], tool_input),
            "session_id": _str(data.get("session_id")),
            "transcript_path": _str(data.get("transcript_path")),
        }
    if source == "opencode":
        props = data.get("properties")
        if not isinstance(props, dict):
            return None
        if data.get("type") == "permission.asked":
            if data.get("parentID"):
                return None
            patterns = props.get("patterns")
            detail = ", ".join(p for p in patterns if isinstance(p, str)) if isinstance(patterns, list) else None
            kind, tool_name = "permission", _str(props.get("permission"))
        elif data.get("type") == "question.asked":
            questions = props.get("questions")
            first = questions[0] if isinstance(questions, list) and questions else None
            detail = _str(first.get("question")) if isinstance(first, dict) else None
            kind, tool_name = "question", None
        else:
            return None
        return {
            "kind": kind,
            "tool_name": tool_name,
            "detail": detail or None,
            "discriminator": _discriminator(props.get("id"), tool_name, props),
            "session_id": _str(props.get("sessionID")),
            "transcript_path": None,
        }
    if source == "dsh":
        # o perfil headless do dsh 0.2.1-rc.5 não instala hooks nem pede aprovação com `danger-full-access`; um
        # formato desconhecido é ignorado em vez de virar um `needs_input` inventado
        return None
    return None


def _log(task_dir: str, message: str) -> None:
    from datetime import UTC, datetime

    try:
        with open(os.path.join(task_dir, "kit.log"), "a", encoding="utf-8") as f:
            f.write(f"{datetime.now(UTC).isoformat(timespec='seconds').replace('+00:00', 'Z')} emit: {message}\n")
    except OSError:
        pass


def _emit(source: str, task_id: str, task_dir: str) -> None:
    from pathlib import Path

    try:
        data = json.loads(sys.stdin.read())
    except ValueError as e:
        _log(task_dir, f"--from {source}: stdin is not JSON: {e}")
        return
    asked = normalize(source, data)
    if asked is None:
        return

    from grokbot_kit import config, deliver, payload

    directory = Path(task_dir)
    meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
    if meta.get("plugin"):
        # numa tarefa de plugin a negação é esperada e não muda o status (plugins, AC 44)
        _log(task_dir, f"--from {source}: {asked['kind']} request in a plugin task, not sent: {asked['tool_name']}")
        return
    event = payload.needs_input_event(
        meta,
        directory,
        kind=str(asked["kind"]),
        tool_name=asked["tool_name"],
        detail=asked["detail"],
        session_id=asked["session_id"],
        transcript_path=asked["transcript_path"],
    )
    deliver.deliver(directory, config.load(), meta["target"], event, str(asked["discriminator"]))


def main(argv: list[str] | None = None) -> int:
    task_id = os.environ.get("GROKBOT_KIT_TASK_ID")
    if not task_id:
        return 0
    args = sys.argv[1:] if argv is None else argv
    source = args[1] if len(args) == 2 and args[0] == "--from" else None
    task_dir = os.environ.get("GROKBOT_KIT_TASK_DIR") or os.path.join(
        os.path.expanduser("~"), ".grokbot-kit", "tasks", task_id
    )
    try:
        if source not in SOURCES:
            _log(task_dir, f"usage: grokbot-kit emit --from {{{','.join(SOURCES)}}}, got {args!r}")
        else:
            _emit(source, task_id, task_dir)
    except Exception as e:  # noqa: BLE001 - o hook nunca pode falhar o agente (AC 60)
        _log(task_dir, f"--from {source}: {type(e).__name__}: {e}")
    sys.stdout.write("{}")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())

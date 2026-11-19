"""Node adapter for the shared Jobsearch parser library.

The parser implementation lives in the jobsearch repository
(``api/_lib/parsers/ris.mjs``) and is exposed through
``scripts/ris-parser-cli.mjs``. This module is the only integration point:
it runs the CLI with JSON over stdin/stdout, enforces limits and maps errors.

No network, no shell, no secret access. The CLI path and node binary are
explicit (environment or injection); a missing runtime fails closed.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Optional

PARSER_SCHEMA_VERSION = "1.0"
SUPPORTED_CAPABILITIES = ("parse.cv", "parse.job")
MAX_PAYLOAD_CHARS = 100_000
DEFAULT_TIMEOUT_SECONDS = 15


class ParserError(RuntimeError):
    """Base class for parser integration errors."""

    code = "parser_error"


class ParserInputError(ParserError):
    """The input is invalid; retrying the same payload will not help."""

    code = "invalid_input"


class ParserUnavailable(ParserError):
    """The parser runtime is missing, timed out or broke; retry may help."""

    code = "parser_unavailable"


@dataclass(frozen=True)
class ParserResult:
    schema_version: str
    capability: str
    parser_version: str
    data: Dict[str, Any]
    confidence: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "schemaVersion": self.schema_version,
            "capability": self.capability,
            "parserVersion": self.parser_version,
            "data": self.data,
            "confidence": self.confidence,
        }


Runner = Callable[[str, Dict[str, Any]], Dict[str, Any]]


def _validate_envelope(capability: str, payload: Any) -> ParserResult:
    if not isinstance(payload, dict):
        raise ParserUnavailable("parser returned a non-object response")
    if payload.get("capability") != capability:
        raise ParserUnavailable("parser returned a different capability")
    if payload.get("schemaVersion") != PARSER_SCHEMA_VERSION:
        raise ParserUnavailable("parser schema version mismatch")
    data = payload.get("data")
    confidence = payload.get("confidence")
    if not isinstance(data, dict) or not isinstance(confidence, dict):
        raise ParserUnavailable("parser response is missing data/confidence")
    version = payload.get("parserVersion")
    if not isinstance(version, str) or not version:
        raise ParserUnavailable("parser response is missing parserVersion")
    return ParserResult(
        schema_version=PARSER_SCHEMA_VERSION,
        capability=capability,
        parser_version=version,
        data=data,
        confidence=confidence,
    )


def _map_cli_error(stdout: str) -> ParserError:
    try:
        payload = json.loads(stdout)
    except ValueError:
        return ParserUnavailable("parser CLI failed without a JSON error")
    error = (payload or {}).get("error") or {}
    code = str(error.get("code") or "parser_error")
    message = str(error.get("message") or "parser CLI failed")
    if code in ("invalid_input", "too_large", "unsupported_capability"):
        return ParserInputError(f"{code}: {message}")
    return ParserUnavailable(f"{code}: {message}")


def parse_via_node(
    capability: str,
    payload: Dict[str, Any],
    *,
    cli: Optional[str] = None,
    node: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    runner: Optional[Runner] = None,
) -> ParserResult:
    """Run the shared parser CLI and return a validated result.

    ``runner`` is an injection point for tests and alternate transports
    (e.g. an internal Node Lambda). It receives ``(capability, payload)`` and
    returns the CLI-shaped JSON object.
    """
    if capability not in SUPPORTED_CAPABILITIES:
        raise ParserInputError(f"unsupported capability: {capability}")
    if not isinstance(payload, dict):
        raise ParserInputError("payload must be an object")
    encoded = json.dumps({"input": payload}, ensure_ascii=False)
    if len(encoded) > MAX_PAYLOAD_CHARS:
        raise ParserInputError("payload exceeds the parser size limit")

    if runner is not None:
        try:
            return _validate_envelope(capability, runner(capability, payload))
        except ParserError:
            raise
        except Exception as exc:  # noqa: BLE001 - boundary
            raise ParserUnavailable(
                f"parser runner failed: {type(exc).__name__}") from exc

    cli_path = cli or os.environ.get("RIS_PARSER_CLI", "")
    if not cli_path or not Path(cli_path).is_file():
        raise ParserUnavailable(
            "RIS_PARSER_CLI is not configured (shared parser CLI missing)")
    node_bin = node or os.environ.get("RIS_PARSER_NODE") or shutil.which("node")
    if not node_bin:
        raise ParserUnavailable(
            "node runtime not available; the Python Lambda cannot run the "
            "shared parser CLI")

    try:
        proc = subprocess.run(  # noqa: S603 - fixed binary, no shell
            [node_bin, cli_path, "--capability", capability],
            input=encoded,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise ParserUnavailable("parser CLI timed out") from exc
    except OSError as exc:
        raise ParserUnavailable(
            f"parser CLI could not start: {type(exc).__name__}") from exc

    if proc.returncode != 0:
        raise _map_cli_error(proc.stdout)
    try:
        payload_out = json.loads(proc.stdout)
    except ValueError as exc:
        raise ParserUnavailable("parser CLI returned invalid JSON") from exc
    return _validate_envelope(capability, payload_out)


__all__ = [
    "MAX_PAYLOAD_CHARS",
    "PARSER_SCHEMA_VERSION",
    "SUPPORTED_CAPABILITIES",
    "ParserError",
    "ParserInputError",
    "ParserResult",
    "ParserUnavailable",
    "parse_via_node",
]

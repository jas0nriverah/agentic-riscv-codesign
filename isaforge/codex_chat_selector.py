"""Interactive bridge for using the current Codex model as a bounded selector.

This is a development bridge, not a callable model API. The chat model receives
one allowlisted request and returns one JSON tool action per turn. The local
host retains charge accounting, hidden replay outcomes, and final acceptance.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
import time
from typing import TextIO

from .selection_provider import PROTOCOL, _valid_action


class CodexChatBridgeError(RuntimeError):
    """Invalid or unavailable action from the interactive chat bridge."""


class CodexChatSelectionProvider:
    """One JSON action per active Codex turn, with no automatic retries."""

    def __init__(self, *, input_stream: TextIO | None = None,
                 output_stream: TextIO | None = None,
                 model_label: str = 'current Codex chat model; deployment ID unavailable',
                 max_request_bytes: int = 300_000,
                 max_action_bytes: int = 10_000, request_directory: Path | None = None):
        if not isinstance(model_label, str) or not model_label.strip():
            raise ValueError('model_label must be a nonempty string')
        if type(max_request_bytes) is not int or not 1 <= max_request_bytes <= 1_000_000:
            raise ValueError('max_request_bytes is outside the supported bound')
        if type(max_action_bytes) is not int or not 1 <= max_action_bytes <= 100_000:
            raise ValueError('max_action_bytes is outside the supported bound')
        self.input_stream = input_stream or sys.stdin
        self.output_stream = output_stream or sys.stdout
        self.max_request_bytes = max_request_bytes
        self.max_action_bytes = max_action_bytes
        self.request_directory = request_directory
        if request_directory is not None:
            Path(request_directory).mkdir(parents=True, exist_ok=False)
        self.calls = 0
        self.last_usage = {}
        self.last_elapsed_seconds = 0.0
        self.identity = dict(provider='codex-chat-bridge', model_label=model_label,
            model_id_available=False, protocol=PROTOCOL,
            tools=['list_candidates', 'predict', 'measure', 'finalize'],
            isolation='serialized-allowlist-by-caller; active Codex session has broader workspace tools')

    def choose(self, request: dict) -> dict:
        if type(request) is not dict:
            raise CodexChatBridgeError('selector request must be a JSON object')
        try:
            body = json.dumps(request, sort_keys=True, ensure_ascii=False,
                              allow_nan=False, separators=(',', ':'))
        except (TypeError, ValueError):
            raise CodexChatBridgeError('selector request must contain finite JSON values') from None
        encoded = body.encode('utf-8')
        if len(encoded) > self.max_request_bytes:
            raise CodexChatBridgeError('selector request exceeds the bridge byte limit')

        self.calls += 1
        self.last_usage = {}
        started = time.monotonic()
        if self.request_directory is not None:
            request_path = Path(self.request_directory)/f'public-{self.calls:02d}.json'
            with request_path.open('x') as handle:
                handle.write(body)
            self.output_stream.write(f'PUBLIC_REQUEST_FILE={request_path}\nACTION_JSON> ')
        else:
            self._write_request(body, encoded)
        self.output_stream.flush()
        line = self.input_stream.readline(self.max_action_bytes + 2)
        self.last_elapsed_seconds = time.monotonic() - started
        return self._parse_action(line)

    def _write_request(self, body, encoded):
        self.output_stream.write(
            f'\nISAForge Codex selector request {self.calls} ({len(encoded)} bytes)\n'
            'Return exactly one JSON line: {"tool":"...","arguments":{...}}\n'
            'Copy the complete candidate_id exactly; never shorten it.\n'
            'BEGIN_PUBLIC_REQUEST\n'
        )
        self.output_stream.write(body + '\nEND_PUBLIC_REQUEST\nACTION_JSON> ')

    def _parse_action(self, line):
        if not line:
            raise CodexChatBridgeError('no action received; session stopped without retry')
        if len(line.encode('utf-8')) > self.max_action_bytes:
            raise CodexChatBridgeError('action exceeds the bridge byte limit')
        try:
            action = json.loads(line)
        except (ValueError, TypeError):
            raise CodexChatBridgeError('action must be one JSON object; session stopped without retry') from None
        if (type(action) is not dict or set(action) != {'tool', 'arguments'} or
                type(action['tool']) is not str or type(action['arguments']) is not dict or
                not _valid_action(action['tool'], action['arguments'])):
            raise CodexChatBridgeError('action violates the four-tool schema; session stopped without retry')
        return action

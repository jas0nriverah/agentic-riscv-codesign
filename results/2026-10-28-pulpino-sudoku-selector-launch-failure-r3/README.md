# PULPino Sudoku relay launch failure — r2 snapshot r3

The zero-label agent process was launched without a PTY. The bridge returned `CodexChatBridgeError` before a usable structured action, and the host finalized baseline fallback. The saved ledger keeps the exception class but not its message, so EOF is the likely cause inferred from the pipe invocation rather than a separately recorded error string. No provider response, tool call, candidate attempt, or target label occurred.

The original agent request, ledger, report, protocol, and SQLite projection are preserved under `agent/`. This is a failed launch, not a selection result. The corrected r4 experiment checks for a live PTY before creating an episode.

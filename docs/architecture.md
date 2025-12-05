## Codex CLI Internal Workflow

This document describes the high-level internal workflow of the Rust Codex CLI: how the TUI and non-interactive modes talk to the app server and core, how tool calls are executed, and how safety features like ghost snapshots fit into the picture.

### 1. Startup

- You launch either:
  - `codex` (interactive TUI), or
  - `codex exec "your prompt"` (non-interactive / CI).
- The `codex-tui` binary:
  - Loads configuration (`~/.codex/config.toml`, AGENTS.md, environment variables).
  - Initializes logging (`RUST_LOG`) and telemetry.
  - Starts the local **app server** process.
  - Connects to the app server over a local channel.

### 2. App Server and Core Session

- The **app server** (`codex-rs/app-server`) brokers between the UI and the reasoning engine:
  - Validates config, authentication, sandbox, and approval policy.
  - Starts a **Codex core session** (`codex-rs/core`) with:
    - A conversation / thread ID.
    - Feature flags (ghost snapshots, undo, etc.).
    - A model client (`codex-api`) configured to talk to your provider.

### 3. First Turn

- The UI (TUI or `exec`) sends a **turn** to the app server:
  - Prompt text and any attachments.
  - Current plan (if any) and settings.
- The app server forwards the turn to **core**, which:
  - May start a background **ghost snapshot** task (see below).
  - Builds the tool list (shell, `apply_patch`, MCP tools, etc.).
  - Constructs a chat-completions request via `codex-api` and opens an SSE stream to the model.

### 4. Streaming Responses and Events

As the model responds over SSE, core receives **response items** and converts them into internal events (logged under `handle_codex_event`):

- Reasoning:
  - `Reasoning` / `ReasoningContentDelta` – structured reasoning summaries, e.g. “Updating progress plan…”.
  - `ReasoningRawContentDelta` – raw reasoning text when enabled.
- User-visible messages:
  - `AgentMessageContentDelta` – the assistant text you see in the UI.
- Tool calls:
  - `FunctionCall` / `ToolCall` – requests like `update_plan`, `shell`, `apply_patch`, `mcp-tool`, etc.
  - `FunctionCallOutput` – the result of executing a tool.
- Accounting:
  - `TokenCount` – token usage and context window updates.
- Background work:
  - `GhostSnapshot` – results of a ghost snapshot (or a no-op in non-git directories).

The app server translates these into **server notifications** for the UI.

### 5. Tool Execution and Approvals

When the model decides to call a tool:

- The app server checks the **approval policy**:
  - Modes like `suggest` / `untrusted` require explicit confirmation for writes and shell.
  - `auto-edit` automatically applies `apply_patch` changes but still prompts before running shell commands.
  - `full-auto` automatically runs both writes and commands in a sandbox.
- If a call is allowed:
  - Shell commands are executed inside the platform sandbox (e.g. Seatbelt on macOS).
  - File modifications are applied via `apply_patch` and respect execpolicy rules.
- The tool’s result is returned as `FunctionCallOutput` and fed back into the model so it can continue the turn.

### 6. Plan Management

- The model maintains a plan using the `update_plan` tool:
  - Emits `update_plan` calls with a list of steps, each with a status (`pending`, `in_progress`, `completed`).
  - Core and the app server update the persistent plan state.
  - The TUI displays these steps and their statuses.
- Reasoning items (e.g. “Updating progress plan…”) explain why the plan is being adjusted.

### 7. Ghost Snapshots and Undo

- For sessions that can write to the repo and when the feature is enabled, core may start a **ghost snapshot** task:
  - Subscribes to a “tool gate” so tools wait until the snapshot attempt finishes.
  - Runs Git plumbing in a blocking pool to capture a hidden “ghost commit” of the working tree.
  - Emits log lines such as:
    - `spawning ghost snapshot task`
    - `ghost snapshot blocking task finished`
    - `ghost commit captured: <hash>`
    - `ghost snapshot gate marked ready`
- Later, undo operations can restore from this hidden commit without cluttering the visible Git history.

### 8. Turn Completion and Next Steps

- When the model finishes a turn:
  - Core emits `ItemCompleted` events for reasoning, messages, and tool calls.
  - The app server forwards final events; the UI shows:
    - Assistant messages and reasoning (if enabled).
    - Diffs for file changes and any tool output.
    - Updated plan state.
- You can:
  - Approve or reject changes.
  - Run your own commands.
  - Send another prompt, which starts the next turn on the same thread.

### 9. `codex exec` Differences

- `codex exec` uses the same app server and core machinery but:
  - Does not start the TUI; output goes directly to the terminal.
  - Defaults to `RUST_LOG=error` and prints logs inline, rather than to the TUI log file.
  - Is designed for CI and other non-interactive workflows.


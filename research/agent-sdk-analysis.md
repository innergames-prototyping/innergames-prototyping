# Running the v5 analysis through the Claude Agent SDK

Ticket: #128. Question: can the `claude -p` call in `backend/app/pipeline.py` (branch `feature/extraction-to-simulation`) become a Claude Agent SDK session, and what does that change?

Sources:

- SDK source: `claude-agent-sdk` 0.2.180 (the version in `backend/uv.lock` on `origin/staging`; `backend/pyproject.toml` asks `>=0.2.180`), sdist from PyPI, files under `src/claude_agent_sdk/`. `uv` is not installed on this machine, so the sdist was unpacked instead of `uv sync`.
- CLI: `claude --help` of Claude Code 2.1.328 (local). The wheel bundles CLI 2.1.321 (`_cli_version.py`). I did not run the bundled binary, so "does the bundled CLI know `--safe-mode`" is unverified.
- Docs: code.claude.com `agent-sdk/overview`, `agent-sdk/python`, `agent-sdk/cost-tracking`, `cli-reference`, `env-vars`, `legal-and-compliance`.

## 1. Flag to option table

The SDK always starts the CLI as `claude --output-format stream-json --verbose ... --input-format stream-json` (`_internal/transport/subprocess_cli.py`, `_build_command`, around line 574). So `--output-format stream-json` and `--verbose` come for free, and `-p` is replaced by the SDK's streaming stdin protocol.

| `claude -p` flag or setting | SDK equivalent (`ClaudeAgentOptions`) | Note |
|---|---|---|
| `-p "Read 00a_START_HERE.md ..."` | `query(prompt=..., options=...)` | Prompt goes over stdin, not argv. |
| `--safe-mode` | None. Use `env={"CLAUDE_CODE_SAFE_MODE": "1"}`, or `extra_args={"safe-mode": None}` | `--safe-mode` "Sets `CLAUDE_CODE_SAFE_MODE=1`" (`claude --help`; env-vars page). Both routes work only if the CLI the SDK launches knows the flag or variable (see the version risk below). |
| `--strict-mcp-config` | `strict_mcp_config=True` | Direct. Appends `--strict-mcp-config`. |
| `--no-chrome` | None. Use `extra_args={"no-chrome": None}` | Or env `CLAUDE_CODE_ENABLE_CFC=0` (env-vars page: `0` starts with Chrome integration off). Safe mode already disables MCP servers and plugins, but the docs do not say it turns off Chrome, so keep this one. |
| `--disable-slash-commands` | None. Use `extra_args={"disable-slash-commands": None}` | No env variable found in the env-vars page. `--safe-mode` also disables skills and custom commands. |
| `--model claude-opus-5-5` | `model="claude-opus-5-5"` | Direct. Also `fallback_model`. |
| `--effort high` | `effort="high"` | Direct. Type `EffortLevel = low, medium, high, xhigh, max` (`types.py` line 37). |
| `--tools Bash,Read,Write,Edit` | `tools=["Bash", "Read", "Write", "Edit"]` | Direct. Joined with commas. `[]` gives `--tools ""` (what extraction uses). |
| `--permission-mode acceptEdits` | `permission_mode="acceptEdits"` | Direct. Literal also allows `default, plan, bypassPermissions, dontAsk, auto`. |
| `--allowedTools Bash` | `allowed_tools=["Bash"]` | Direct. |
| `--append-system-prompt <ENVIRONMENT>` | `system_prompt={"type": "preset", "preset": "claude_code", "append": ENVIRONMENT}` | Direct, but see the trap below. |
| `--output-format stream-json`, `--verbose` | Built in | Always on. |
| cwd of the subprocess | `cwd=simulation` | Direct. The SDK also sets `PWD`. |
| env `PYTHONDONTWRITEBYTECODE=1` | `env={"PYTHONDONTWRITEBYTECODE": "1", ...}` | Direct. `options.env` is merged over `os.environ` (SDK passes the parent env on, minus `CLAUDECODE`). |

Traps, from the source:

- System prompt. With `system_prompt=None` the SDK sends `--system-prompt ""`, so the session has no Claude Code prompt. A plain string replaces the Claude Code prompt. Only the `preset` form with `append` maps to `--append-system-prompt` and keeps the default prompt, which is what the `claude -p` command does today. Type: `SystemPromptPreset` (`types.py` line 40).
- Setting sources. `setting_sources=None` makes the SDK pass nothing, and the CLI then loads its default sources. In `_apply_skills_defaults`, `["user", "project"]` is the default only when `skills` is set. Set `setting_sources=[]` to load no user, project or local settings (extraction does this). `--safe-mode` already disables settings customizations, so this is belt and braces.
- Bundled CLI. `_find_cli` picks the bundled binary first and only then `shutil.which("claude")`. The wheel bundles 2.1.321. The local CLI is 2.1.328. If 2.1.321 does not know `--safe-mode`, `--no-chrome` or `--disable-slash-commands`, the session fails at start with an unknown option. Test once with `claude --help` from the bundled path (`claude_agent_sdk/_bundled/claude`), or set `cli_path` to the installed `claude`. Also note the CLI is a separate install from the Python package in Docker.
- `extra_args` renders `{"flag": None}` as `--flag`, and `{"flag": "value"}` as `--flag value`.
- Permission denials do not stop a session. With `acceptEdits` and `allowed_tools=["Bash"]`, a tool outside both is auto-denied in non-interactive mode, the same as with `-p`. Read `ResultMessage.permission_denials` to see it.
- Streaming. `query()` yields typed messages (`SystemMessage`, `AssistantMessage`, `UserMessage`, `ResultMessage`) instead of JSON lines. `pipeline.py` writes `claude.jsonl` and parses the last `result` event. With the SDK, keep the final `ResultMessage` and write the log from the messages if you still want a file. `ResultMessage.result` carries the text that `pipeline.py` scans for `RUNLOG:` lines.

Sketch:

```python
options = ClaudeAgentOptions(
    model="claude-opus-5-5",
    effort="high",
    tools=["Bash", "Read", "Write", "Edit"],
    allowed_tools=["Bash"],
    permission_mode="acceptEdits",
    system_prompt={"type": "preset", "preset": "claude_code", "append": ENVIRONMENT},
    strict_mcp_config=True,
    setting_sources=[],
    cwd=simulation,
    env={"PYTHONDONTWRITEBYTECODE": "1", "CLAUDE_CODE_SAFE_MODE": "1", "CLAUDE_CODE_ENABLE_CFC": "0"},
    extra_args={"disable-slash-commands": None, "no-chrome": None},  # safe-mode via env above
)
```

## 2. Subscription login without `ANTHROPIC_API_KEY`

Yes, technically. The SDK does not authenticate itself. It starts the Claude Code CLI as a subprocess and passes on the parent environment (`subprocess_cli.py`, `connect`: `inherited_env` plus `options.env`). The SDK source has no code that reads or requires an API key. The CLI then uses what it finds: an API key if one is set, otherwise the claude.ai OAuth login in `~/.claude/.credentials.json` (macOS: Keychain, service "Claude Code-credentials", see `_internal/session_resume.py`).

Evidence:

- `SystemMessage` init field `apiKeySource` (`types.py` line 1495): values `ANTHROPIC_API_KEY`, `apiKeyHelper`, `/login managed key`, or `"none"` described as "no API key in use, e.g. a claude.ai login". The session can be checked at run time by reading it from the init message.
- env-vars page: `ANTHROPIC_API_KEY` "is used instead of your Claude Pro, Max, Ultra, Team, or Enterprise subscription even if you are logged in. In non-interactive mode (`-p`), the key is always used when" it is set. So never leave a key in the environment if the run must use the subscription. Use `env` in the options or unset it to be sure.
- `CLAUDE_CODE_SIMPLE` / `--bare` skip OAuth and keychain reads (env-vars page). Do not use them for a subscription run. `--safe-mode` keeps auth ("Auth, model selection, built-in tools and plugins, and permissions work normally", `claude --help`).
- Check on this machine (DevBox), 2026-11-19: `claude auth status` shows `loggedIn: true`, `authMethod: "claude.ai"`, and no `ANTHROPIC_API_KEY` is set in the environment. `claude -p "say ok" --model haiku` answered `OK`. That proves the CLI runs on the login. It does not run through the SDK, but the SDK only spawns the same CLI.

Policy caveat (docs, not code). The Agent SDK overview says: "Unless previously approved, Anthropic does not allow third party developers to offer claude.ai login or rate limits for their products, including agents built on the Claude Agent SDK." The legal page says developers building products on the Agent SDK "should use API key authentication", and may not route requests through Free, Pro, Max or Ultra plan credentials on behalf of their users. The same page allows a user to sign in to the unmodified Claude Code binary with their own subscription. Reading: a team member running the pipeline on their own machine with their own login is the use the docs allow. A hosted service, or one login that serves other users, is not. Treat the hosted backend case as needing an API key (or a decision from the owner).

Practical limit: a Max/Ultra plan has usage windows and rate limits. A v5 run with Opus at `high` effort will draw from that allowance, and a 429 can come back (`ResultMessage.api_error_status`). `reader.py` already handles 429 with back-off.

## 3. Cost and usage reporting

`ResultMessage` (`types.py` line 1706):

| Field | Meaning |
|---|---|
| `total_cost_usd: float or None` | Cumulative cost estimate for the whole `query()` call, subagents included. |
| `usage: dict or None` | Token counts of the main loop only (`input_tokens`, `output_tokens`, cache fields). Excludes subagents. |
| `model_usage: dict[str, ModelUsage] or None` | Per model: `inputTokens`, `outputTokens`, `cacheReadInputTokens`, `cacheCreationInputTokens`, `webSearchRequests`, `costUSD`, `contextWindow`, `maxOutputTokens`. camelCase keys. Covers every model call, including subagents and compaction. |
| `duration_ms`, `duration_api_ms`, `num_turns` | Time and turns. |
| `is_error`, `subtype`, `stop_reason`, `terminal_reason`, `errors`, `api_error_status`, `permission_denials`, `session_id` | Outcome. |

Is cost meaningful on a subscription? Not as money. The cost-tracking docs say `total_cost_usd` and `costUSD` "are client-side estimates, not authoritative billing data", computed locally from a bundled price table, and "Don't bill end users or trigger financial decisions from these fields". On a subscription there is no per-token bill, so the number is a list-price equivalent: useful to compare runs and to size the load on the plan, not a charge. Token counts (`usage`, `model_usage`) are the more honest unit. Both fields are optional in Python, so use `or 0` as `agent.py` does. `pipeline.py` also adds the reader `cost_usd` files from `work/**/reads`; those are the same kind of estimate.

## 4. What staging already does

`backend/app/claude.py` has `isolated_options(...)`, used by every SDK session:

- `setting_sources=[]`, `strict_mcp_config=True`, `tools=[]`, `permission_mode="dontAsk"`, `allowed_tools` from the caller.
- `env=ISOLATED_ENV` (`CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`, `ENABLE_CLAUDEAI_MCP_SERVERS=false`).
- `system_prompt` as a plain string (replaces the Claude Code prompt), `model`, `cwd`, `mcp_servers`, optional `output_format` JSON schema, `max_turns`, and `max_buffer_size=2**26` for base64 images.

`backend/app/extraction/agent.py` calls `query(prompt, options)` with those options and an in-process MCP server (`build_server`), reads `AssistantMessage` blocks for progress and takes `ResultMessage.result`, `.total_cost_usd or 0` and `.is_error`. `reader.py` does the same per call with 429 back-off, a timeout and `result.structured_output`. Nothing sets `ANTHROPIC_API_KEY`, `cli_path`, `effort` or `extra_args`, so extraction already runs on whichever login or key the CLI finds.

Reuse as is:

- The isolation idea and the cost and error handling in `agent.py` (`AgentResult`, `or 0`).
- `MAX_MESSAGE_BYTES` and `ISOLATED_ENV` (keeps auto memory and claude.ai MCP servers out).
- The `query()` loop and `ResultMessage` handling.

Needs a variant, not a copy:

- `isolated_options` hard-codes `tools=[]`, `permission_mode="dontAsk"`, a string `system_prompt` and no `effort`/`extra_args`. The analysis needs `tools=[Bash, Read, Write, Edit]`, `acceptEdits`, the `preset` + `append` prompt, `effort="high"` and the three extra flags. Add parameters (`tools`, `permission_mode`, `effort`, `extra_args`, `append_system_prompt`) rather than a second function, or build `ClaudeAgentOptions` directly in the analysis module and reuse only `ISOLATED_ENV` and `MAX_MESSAGE_BYTES`.
- `ISOLATED_ENV` should be merged with `PYTHONDONTWRITEBYTECODE=1` and `CLAUDE_CODE_SAFE_MODE=1`.
- The analysis session needs the real file tools in `cwd`, unlike extraction, which has only MCP tools.

## Open points

- Verify the bundled CLI (2.1.321) accepts `--safe-mode`, `--no-chrome`, `--disable-slash-commands`; otherwise set `cli_path`.
- Decide on auth for any hosted run: subscription is fine for a person on their own login, per the docs above, and an API key is the documented route for a service.

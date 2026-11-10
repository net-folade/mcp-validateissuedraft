# validate-issue-draft

An MCP server with one tool, `validate_issue_draft`. It checks proposed issue fields and reports what is valid, missing, or invalid, and whether the draft is ready to create. It has no side effects: it creates nothing and calls no external API.

## Setup

Requires [uv](https://github.com/astral-sh/uv) and Python 3.13+.

```bash
uv sync
```

## Usage

Open the server in the MCP Inspector (requires Node.js):

```bash
uv run mcp dev server.py
```

Run the sample checks in `samples.json`:

```bash
uv run python check_samples.py
```

## Tool

**Input** (all optional, so missing fields are reported instead of rejected):

| field | type | rules |
|---|---|---|
| `title` | string | not blank; warning if over 80 characters |
| `priority` | string | one of `p0`, `p1`, `p2`, `p3` (case-insensitive) |
| `description` | string | not blank; warning if under 20 characters |
| `labels` | list of strings | at least one; each one of `bug`, `billing`, `feature`, `enhancement`, `documentation` |
| `reproduction_steps` | string | not blank |
| `affected_account` | string | not blank |

**Output:**

```json
{
  "valid_fields": {},
  "missing_fields": [],
  "invalid_fields": {},
  "warnings": [],
  "ready_to_create": false
}
```

`ready_to_create` is `true` only when nothing is missing or invalid. Warnings don't block it.

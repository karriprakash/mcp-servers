# Git Pulse Adda MCP

Remote MCP server (HTTP) that returns live GitHub profile data for a resume dashboard.

## Tool

`get_developer_metrics(username, token="")` returns the profile (name, bio, avatar, follower and repo
counts), a language breakdown (number of non-fork repos per language, from the 30 most recently
updated repos) and the top 6 repos by stars.

On failure it returns `{"error": "..."}`. If only the repo list fails, the profile is still
returned with a `warning` field.

## Configuration

| Variable | Purpose | Default |
|---|---|---|
| `PORT` | HTTP port | `8000` (the Dockerfile sets `8080`) |
| `GITHUB_TOKEN` | Raises the API rate limit from 60 to 5,000 requests per hour. A fine-grained token with no extra permissions is enough for public data. | unset |

Set `GITHUB_TOKEN` on the server rather than passing `token` in tool calls; arguments can end up in
client logs and conversation history. Never commit a token.

## Run locally

```bash
pip install -r requirements.txt
GITHUB_TOKEN=... python server.py        # MCP endpoint: http://localhost:8000/mcp
```

## Run with Docker

From the repository root:

```bash
GITHUB_TOKEN=... docker compose up --build git-pulse-adda   # http://localhost:8080/mcp
```

Or build directly: `docker build -t git-pulse-adda servers/git-pulse-adda`.

## Tests

The logic lives in `metrics.py` and is tested with a fake HTTP client, so the tests need neither
network access nor `fastmcp`:

```bash
pytest tests/test_git_pulse_adda.py
```

## Notes

- Usernames are validated against GitHub's rules before being placed in a URL.
- Requests time out after 10 seconds.
- The Docker image runs as a non-root user.

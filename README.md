# MCP Servers

A modular ecosystem of production-ready MCP servers, AI integrations,
automation tools, and intelligent agent workflows.

> **Project status:** Early scaffold. Servers are added incrementally.

## Servers

| Server | Status | Description |
|---|---|---|
| [`git-pulse-adda`](servers/git-pulse-adda/README.md) | runnable (Python, Docker) | Live GitHub profile, top repos and language metrics for a resume dashboard |
| `wedding-cinematic-studio` | placeholder | Wedding-film production workflows |
| `video-production`, `ai-media-tools`, `automation` | placeholder | Reserved |

## Repository layout

```text
servers/
  wedding-cinematic-studio/  Wedding-film production workflows
  video-production/          Video creation and post-production tools
  ai-media-tools/            AI-powered media utilities
  automation/                Reusable automation MCP servers
shared/                      Code and contracts shared by servers
web-ui/                      Web-based management interface
integrations/                Third-party service integrations
tests/                       Unit, integration, and end-to-end tests
docs/                        Architecture and contributor documentation
.github/workflows/           CI and security workflows
docker-compose.yml           Local multi-service orchestration entry point
```

Server packages may use Python or TypeScript. Each server should document its
runtime, configuration, tools, and deployment options in its own directory.

## Getting started

Only `git-pulse-adda` is runnable so far; see its README. Python development
requires Python 3.11 or newer. From the repository root:

```bash
python -m compileall -q servers shared tests
python -m pytest -q
```

TypeScript development requires Node.js 20 or newer:

```bash
npm ci
npm run typecheck
```

Run the containerised servers with Docker Compose:

```bash
GITHUB_TOKEN=... docker compose up --build   # git-pulse-adda on http://localhost:8080/mcp
```

## Development principles

- Keep each MCP server independently understandable and deployable.
- Put genuinely reusable contracts and utilities in `shared/`.
- Keep credentials out of source control; use environment variables or a
  deployment secret manager.
- Add focused tests and update the relevant server documentation with every
  implementation.
- Prefer secure defaults, explicit configuration, and actionable error
  messages.

See [docs/architecture.md](docs/architecture.md) for the initial architecture
and contribution guidance.

## Security

Secret scanning and push protection are enabled for this repository. GitHub
Actions runs code scanning and dependency review; Dependabot is configured for
dependency and Actions updates. Never commit API keys, tokens, or other
credentials.

## License

This project is licensed under the [MIT License](LICENSE).

# MCP Servers

A modular ecosystem of production-ready MCP servers, AI integrations,
automation tools, and intelligent agent workflows.

> **Project status:** This repository is the initial monorepo scaffold.
> Server implementations and runnable containers will be added incrementally.

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

The scaffold does not yet include runnable servers or container services.
Python development requires Python 3.11 or newer. Run the initial syntax check
from the repository root:

```bash
python -m compileall -q servers shared tests
```

Use Docker Compose as server services are added:

```bash
docker compose up --build
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

# Architecture and contribution guide

## Monorepo boundaries

Each directory under `servers/` is a separately scoped MCP server or server
family. A server should own its protocol adapter, configuration, and
server-specific tests. Shared code belongs in `shared/` only when multiple
servers need the same stable contract or implementation.

`integrations/` contains adapters for external services. `web-ui/` is the
management interface and should communicate with server capabilities through
documented interfaces rather than importing server internals.

## Adding a server

1. Add implementation and focused tests under the corresponding `servers/`
   directory.
2. Document supported tools, required configuration, local execution, and
   deployment in that server's README.
3. Add or update CI checks and container configuration when the server becomes
   runnable.
4. Keep credentials in environment variables or a secret manager; provide
   examples using placeholders only.

## Quality and security

Pull requests run the repository CI, dependency review, and code scanning
workflows. Keep dependencies current, avoid committing generated credentials
or local environment files, and add tests for behavior introduced by changes.

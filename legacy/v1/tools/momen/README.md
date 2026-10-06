# Momen MCP bridge — AEGIS tooling

Lets this machine drive the user's Momen projects (the AEGIS dashboard app)
through Momen's official `momen-mcp` MCP server.

## Files

- `mcp_client.py` — minimal MCP-over-stdio JSON-RPC client (no SDK dependency).
- `verify.py` — end-to-end setup check: node/npx, package, server handshake,
  tool surface, auth status. Exit 0 = plumbing healthy.
- `auth_token.py` — stores the user's Momen JWT in `~/.momen-mcp/credentials.json`
  (0600) and verifies it with `auth WHOAMI`. Never prints the token.
- `mcp-config.json` — editor config (Cursor / Claude Desktop) for the same server.

## Setup (run once)

```bash
cd ~/workspace/aegis/tools/momen
python3 verify.py
```

`verify.py` checks everything up to the auth gate. Expected: all PASS, with
"Momen auth … not authenticated yet".

## Authenticate (needs the user, one time)

The Momen login is an interactive browser OAuth flow, so it runs on the
**user's** machine:

1. User runs `npx -y momen-mcp@2.7.13 login` and logs into Momen in the browser.
2. User copies the `access_token` value from `~/.momen-mcp/credentials.json`.
3. Here: `python3 auth_token.py` and paste it (no echo). The script writes
   `~/.momen-mcp/credentials.json` (0600) and verifies with WHOAMI.

The token is a JWT — time-limited, revocable from Momen at any time.
Never commit it; the credentials file lives outside the repo.

## Use

```python
from mcp_client import MCPClient
c = MCPClient(["npx", "-y", "momen-mcp@2.7.13", "mcp", "--no-daemon"])
c.initialize(); c.notify("notifications/initialized")
c.tool_call("get_projects", {})
c.tool_call("set_current_project", {"projectId": "<id>"})
c.tool_call("project_inspect", {"op": "DETAIL"})
c.close()
```

Key tools: `get_projects`, `set_current_project`, `project_inspect`
(DETAIL/METADATA/RESOURCES), `schema_session` (LOAD/SYNC/VALIDATE),
`sync_backend` (deploy), `runtime_graphql` (data), `search_docs`.

# Installing the VX MCP server

This guide walks through wiring the VX MCP server into an MCP
client (Claude Code, Claude Desktop) so the agent can drive VX
directly.

---

## 1. Prerequisites

- VX installed and runnable (see the
  [main README](../README.md) → "Quick install").
- Python 3.10 or newer on `PATH`.
- An MCP-capable client, such as:
  - Claude Code (CLI)
  - Claude Desktop (GUI)
- (Optional) A virtualenv tool: `venv` is fine, `uv` works too.

---

## 2. Set up the Python environment

From this folder (`mcp/`):

```bash
python -m venv .venv
source .venv/bin/activate          # macOS / Linux
# .venv\Scripts\activate            # Windows PowerShell

pip install -r requirements.txt
```

Note the absolute path of `vx_mcp_server.py` and the absolute path
of the `python` binary inside `.venv/bin/` (`.venv\Scripts\` on
Windows). You'll need both for the client config.

```bash
realpath vx_mcp_server.py           # /…/mcp/vx_mcp_server.py
realpath .venv/bin/python           # /…/mcp/.venv/bin/python
```

---

## 3a. Wire up Claude Code

Register the server with Claude Code's `claude mcp add` command
(add `--scope user` to have it in every project):

```bash
claude mcp add vx -- /absolute/path/to/mcp/.venv/bin/python /absolute/path/to/mcp/vx_mcp_server.py
```

Or, for one project, put a `.mcp.json` file at the project's root:

```json
{
  "mcpServers": {
    "vx": {
      "command": "/absolute/path/to/mcp/.venv/bin/python",
      "args": [
        "/absolute/path/to/mcp/vx_mcp_server.py"
      ]
    }
  }
}
```

Restart `claude` and you should see VX tools in the agent's tool
list (e.g. `mcp__vx__vx_ping`).

## 3b. Wire up Claude Desktop

Same idea, different file path:

```
~/Library/Application Support/Claude/claude_desktop_config.json     (macOS)
%APPDATA%\Claude\claude_desktop_config.json                         (Windows)
```

Edit the `mcpServers` block to add the `vx` server with the same
shape as above. Restart Claude Desktop.

---

## 4. Verify

Launch VX. Then ask the agent:

> Ping VX.

You should see the agent call `vx_ping` and receive
`{"status":"ok","app":"VX","api_version":2}`. If you
see a connection error, check that VX is actually running
(`curl -s http://127.0.0.1:9876/ping` should work from the same
machine).

---

## 5. Common issues

- **VX not on port 9876.** VX's port is set in Settings > MCP /
  API, or with `--port N`. Give the server that address in its
  environment, in the client config:
  `"env": {"VX_API_BASE": "http://127.0.0.1:9877"}` beside
  `"command"` and `"args"`.
- **A second VX.** Starting VX while it runs brings the running
  one forward. To run two, start the second with
  `VX_NEW_INSTANCE=1` and its own `--port`, and point a second MCP
  server entry at it with `VX_API_BASE`.
- **Python can't find `fastmcp`.** Ensure your client is launching
  the venv's `python`, not the system one. Use absolute paths in
  the MCP JSON config.
- **Tools appear but every call fails with "Cannot connect to
  VX".** VX must be running BEFORE the client invokes a tool. Many
  MCP clients start the server lazily; the first call will fail if
  VX is not yet up.

---

## 6. Uninstall

Remove the `vx` entry from your client's MCP config (in Claude
Code, `claude mcp remove vx`) and, if you no longer need it,
delete the `.venv` folder. The MCP server has no other footprint
on the system.

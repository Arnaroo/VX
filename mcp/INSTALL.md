# Installing the VX MCP server

This guide walks through wiring the VX MCP server into an MCP
client (Claude Code, Claude Desktop) so the agent can drive VX
directly.

---

## 1. Prerequisites

- VX Genome Viewer installed and runnable (see the
  [main README](../README.md) → "Get the binaries").
- Python 3.10 or newer on `PATH`.
- An MCP-capable client. Tested with:
  - Claude Code (CLI)
  - Claude Desktop (GUI)
- (Optional) A virtualenv tool — `venv` is fine, `uv` works too.

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
of the `python` binary inside `.venv/bin/`. You'll need both for
the client config.

```bash
realpath vx_mcp_server.py           # /…/Repo_upload/mcp/vx_mcp_server.py
realpath .venv/bin/python           # /…/Repo_upload/mcp/.venv/bin/python
```

---

## 3a. Wire up Claude Code

Claude Code reads MCP servers from `~/.config/claude/mcp.json`
(Linux/macOS) or `%APPDATA%\Claude\mcp.json` (Windows). Add a
block like:

```json
{
  "mcpServers": {
    "vx": {
      "command": "/absolute/path/to/Repo_upload/mcp/.venv/bin/python",
      "args": [
        "/absolute/path/to/Repo_upload/mcp/vx_mcp_server.py"
      ]
    }
  }
}
```

Restart `claude` and you should see VX tools in the agent's tool
list (e.g. `mcp__vx__vx_ping`).

## 3b. Wire up Claude Desktop

Same idea, different file path. On macOS:

```
~/Library/Application Support/Claude/claude_desktop_config.json
```

Edit the `mcpServers` block to add the `vx` server with the same
shape as above. Restart Claude Desktop.

---

## 4. Verify

Launch VX. Then ask the agent:

> Ping VX.

You should see the agent call `vx_ping` and receive
`{"status":"ok","app":"VX Genome Viewer","api_version":2}`. If you
see a connection error, check that VX is actually running
(`curl -s http://127.0.0.1:9876/ping` should work from the same
machine).

---

## 5. Common issues

- **VX not on port 9876.** Other VX instances on the same machine
  will fail to bind the API socket and start without it. Close all
  but one VX instance.
- **Python can't find `fastmcp`.** Ensure your client is launching
  the venv's `python`, not the system one. Use absolute paths in
  the MCP JSON config.
- **Tools appear but every call returns "connection refused".**
  VX must be running BEFORE the client invokes a tool. Many MCP
  clients start the server lazily; the first call will fail if VX
  is not yet up.

---

## 6. Uninstall

Remove the `vx` entry from your client's MCP config and (if you no
longer need it) delete the `.venv` folder. The MCP server has no
other footprint on the system.

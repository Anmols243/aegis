#!/usr/bin/env python3
"""Minimal MCP stdio client for talking to momen-mcp.

Usage:
    from mcp_client import MCPClient
    c = MCPClient(["npx", "-y", "momen-mcp@2.7.13", "mcp", "--no-daemon"])
    c.initialize()
    c.call("notifications/initialized")
    tools = c.tools_list()["result"]["tools"]
    r = c.tool_call("auth", {"op": "WHOAMI"})
    c.close()
"""
import json
import subprocess
import sys
import threading
import queue
import itertools
import time


class MCPError(RuntimeError):
    pass


class MCPClient:
    def __init__(self, cmd):
        self.proc = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self._id = itertools.count(1)
        self._responses = {}
        self._lock = threading.Lock()
        t = threading.Thread(target=self._reader, daemon=True)
        t.start()

    def _reader(self):
        for line in self.proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "id" in msg and ("result" in msg or "error" in msg):
                with self._lock:
                    self._responses[msg["id"]] = msg

    def notify(self, method, params=None):
        """Send a JSON-RPC notification (no id, no response expected)."""
        msg = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            msg["params"] = params
        try:
            self.proc.stdin.write(json.dumps(msg) + "\n")
            self.proc.stdin.flush()
        except BrokenPipeError:
            raise MCPError(f"server pipe broken on notify {method}")

    def call(self, method, params=None, timeout=120):
        rid = next(self._id)
        req = {"jsonrpc": "2.0", "id": rid, "method": method}
        if params is not None:
            req["params"] = params
        try:
            self.proc.stdin.write(json.dumps(req) + "\n")
            self.proc.stdin.flush()
        except BrokenPipeError:
            raise MCPError(f"server pipe broken on {method}")
        t0 = time.time()
        while time.time() - t0 < timeout:
            with self._lock:
                msg = self._responses.pop(rid, None)
            if msg is not None:
                if "error" in msg:
                    raise MCPError(f"{method}: {msg['error']}")
                return msg
            time.sleep(0.1)
        raise TimeoutError(f"no response for {method} after {timeout}s")

    def initialize(self):
        return self.call("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {"roots": {}, "sampling": {}},
            "clientInfo": {"name": "aegis-momen-client", "version": "1.0"},
        })

    def tools_list(self):
        return self.call("tools/list", {})

    def tool_call(self, name, arguments, timeout=180):
        return self.call("tools/call",
                         {"name": name, "arguments": arguments},
                         timeout=timeout)

    def close(self):
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()

#!/usr/bin/env python3
"""Phase B (redo): fetch GET_COMPONENT_INFO for every id, YAML-parse the
response blob, save structured info + rebuilt tree."""
import json
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent))
from mcp_client import MCPClient

PROJECT = "l7YRy8q8DR7"
APP = "8bD5JlV4jnX"
PAGE = "tqvfjce6e"
OUT = Path(__file__).parent / "extract"

ids = json.load(open(OUT / "ids.json"))
order = ids["order"]
children_map = ids["children"]
skel = ids["skeleton"]

c = MCPClient(["npx", "-y", "momen-mcp@2.7.13", "mcp", "--no-daemon"])
c.initialize()
c.notify("notifications/initialized")

info_map = {}
for i, cid in enumerate(order):
    try:
        r = c.tool_call(
            "component",
            {"op": "GET_COMPONENT_INFO", "appExId": APP,
             "projectExId": PROJECT, "args": {"componentId": cid}},
            timeout=120)
        txt = r["result"]["content"][0]["text"]
        data = json.loads(txt)
        blob = data["responses"][0] if data.get("responses") else ""
        parsed = yaml.safe_load(blob) if isinstance(blob, str) else blob
        info_map[cid] = parsed or {}
    except Exception as e:
        print(f"info failed {i+1}/{len(order)} {cid}: {type(e).__name__} {e}")
        info_map[cid] = {"_error": str(e)}
    if (i + 1) % 20 == 0:
        print(f"  info {i+1}/{len(order)}")

with open(OUT / "info_parsed.json", "w") as f:
    json.dump(info_map, f, indent=1)


def build(cid):
    info = info_map.get(cid, {})
    node = {"id": cid}
    if isinstance(info, dict):
        for k in ("displayName", "type", "properties", "events",
                  "acceptsInputs", "acceptsVariables"):
            if k in info:
                node[k] = info[k]
        style = info.get("style") or {}
        node["style"] = style.get("values", {})
        if style.get("overrides"):
            node["style_overrides"] = style["overrides"]
    else:
        node.update(skel.get(cid, {}))
    if not node.get("displayName"):
        node.update({k: v for k, v in skel.get(cid, {}).items()
                     if k not in node})
    node["children"] = [build(k) for k in children_map.get(cid, [])]
    return node


tree = build(PAGE)
with open(OUT / "tree.json", "w") as f:
    json.dump(tree, f, indent=1)

print("wrote tree.json")
c.close()

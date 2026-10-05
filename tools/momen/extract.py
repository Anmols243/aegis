#!/usr/bin/env python3
"""Extract the full Momen component tree (read-only) into tree.json.

Walks from the page root via GET_CONTAINER_CHILDREN_INFO, then fetches
GET_COMPONENT_INFO for every component id. Saves a nested tree.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mcp_client import MCPClient

PROJECT = "l7YRy8q8DR7"
APP = "8bD5JlV4jnX"
PAGE = "tqvfjce6e"
OUT = Path(__file__).parent / "extract"
OUT.mkdir(exist_ok=True)

c = MCPClient(["npx", "-y", "momen-mcp@2.7.13", "mcp", "--no-daemon"])
c.initialize()
c.notify("notifications/initialized")


def call(op, args=None, timeout=120):
    payload = {"op": op, "appExId": APP, "projectExId": PROJECT,
               "args": args or {}}
    r = c.tool_call("component", payload, timeout=timeout)
    txt = r["result"]["content"][0]["text"]
    try:
        return json.loads(txt)
    except Exception:
        print("NON-JSON for", op, args, "->", txt[:300])
        raise


def unwrap(resp):
    # GET_CONTAINER_CHILDREN_INFO -> {"responses":[{"container":{...},"children":[{id,...}]}]}
    # error shape -> {"errors":[...], ...} (no children)
    if isinstance(resp, dict) and "responses" in resp:
        out = []
        for r in resp["responses"]:
            if not isinstance(r, dict):
                continue
            for ch in r.get("children", []):
                if isinstance(ch, dict) and ch.get("id"):
                    out.append(ch)
        return out
    if isinstance(resp, dict) and "errors" in resp:
        return []
    if isinstance(resp, dict):
        for k in ("data", "result", "children", "components"):
            if k in resp:
                return resp[k]
    return resp


# ---- phase A: walk the tree ----
# Only LAYOUT_VIEW (flex containers) have regular children. TEXT / BUTTON /
# TEXT_INPUT are leaves; CONDITIONAL_VIEW branches come via GET_COMPONENT_INFO.
children_map = {}   # id -> [child ids]
skel = {}           # id -> {displayName, type}
order = []
CONTAINERS = {"LAYOUT_VIEW"}

def walk(cid, ctype, depth=0):
    order.append(cid)
    if ctype not in CONTAINERS:
        children_map[cid] = []
        return
    try:
        resp = call("GET_CONTAINER_CHILDREN_INFO", {"componentId": cid})
    except Exception as e:
        print("  walk failed for", cid, e)
        children_map[cid] = []
        return
    kids = unwrap(resp)
    ids = []
    if isinstance(kids, list):
        for k in kids:
            if isinstance(k, dict):
                kid = k.get("id") or k.get("componentId")
                if kid:
                    ids.append(kid)
                    # stash skeleton info for notes
                    skel[kid] = {"displayName": k.get("displayName"),
                                 "type": k.get("type")}
            elif isinstance(k, str):
                ids.append(k)
    children_map[cid] = ids
    print("  " * depth + f"{cid} [{ctype}] -> {len(ids)} children")
    for kid in ids:
        if kid not in children_map:
            walk(kid, skel.get(kid, {}).get("type"), depth + 1)

print("walking from page", PAGE)
skel[PAGE] = {"displayName": "Page 1", "type": "LAYOUT_VIEW"}
walk(PAGE, "LAYOUT_VIEW")
print(f"total components: {len(order)}")

with open(OUT / "ids.json", "w") as f:
    json.dump({"order": order, "children": children_map, "skeleton": skel},
              f, indent=1)

# ---- phase B: info for each ----
info_map = {}
for i, cid in enumerate(order):
    try:
        resp = call("GET_COMPONENT_INFO", {"componentId": cid})
        info_map[cid] = unwrap(resp)
    except Exception as e:
        print(f"info failed {i+1}/{len(order)} {cid}: {e}")
        info_map[cid] = {"_error": str(e)}
    if (i + 1) % 20 == 0:
        print(f"  info {i+1}/{len(order)}")

with open(OUT / "info.json", "w") as f:
    json.dump(info_map, f, indent=1)


def build(cid):
    node = {"id": cid}
    info = info_map.get(cid, {})
    if isinstance(info, dict):
        node.update(info)
    node["children"] = [build(k) for k in children_map.get(cid, [])]
    return node


tree = build(PAGE)
with open(OUT / "tree.json", "w") as f:
    json.dump(tree, f, indent=1)

print("wrote", OUT / "tree.json", f"({len(order)} components)")
c.close()

#!/usr/bin/env python3
"""
Hook PostToolUse: cria tag incremental v3.0.0.X sempre que um git push for executado.
"""
import json
import sys
import subprocess
import re

data = json.load(sys.stdin)
cmd = data.get("tool_input", {}).get("command", "")

# Só age em comandos git push que não sejam push de tags
if "git push" not in cmd:
    sys.exit(0)
if re.search(r"push\s+origin\s+v\d", cmd):
    sys.exit(0)

repo = r"c:\Users\campe\projetos-claude-code\JtasksApp"

result = subprocess.run(
    ["git", "-C", repo, "tag", "--list", "v*.*.*.*", "--sort=-version:refname"],
    capture_output=True,
    text=True,
)

tags = [
    t.strip()
    for t in result.stdout.strip().split("\n")
    if re.match(r"^v\d+\.\d+\.\d+\.\d+$", t.strip())
]

if tags:
    last = tags[0]
    parts = last.lstrip("v").split(".")
    parts[-1] = str(int(parts[-1]) + 1)
    new_tag = "v" + ".".join(parts)
else:
    new_tag = "v3.0.0.1"

subprocess.run(["git", "-C", repo, "tag", new_tag])
subprocess.run(["git", "-C", repo, "push", "origin", new_tag])
print(json.dumps({"systemMessage": f"Tag {new_tag} criada e enviada ao GitHub"}))

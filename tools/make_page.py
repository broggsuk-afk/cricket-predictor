#!/usr/bin/env python3
"""Build index.html (the page you upload to cPanel) from tools/page_template.html.

Run tools/build.py first. The latest data/index.json is built into the page as a
fallback copy; visitors normally get fresh data from GitHub when the page loads.
Only needed when the page design changes - the daily update does not touch it.
"""
import json, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
tpl = open(os.path.join(ROOT, "tools", "page_template.html"), encoding="utf-8").read()
data = json.load(open(os.path.join(ROOT, "data", "index.json"), encoding="utf-8"))
out = tpl.replace("__SEED__", json.dumps(data, ensure_ascii=False).replace("</", "<\\/"))
open(os.path.join(ROOT, "index.html"), "w", encoding="utf-8").write(out)
print("wrote index.html")

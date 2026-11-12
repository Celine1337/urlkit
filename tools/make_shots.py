#!/usr/bin/env python3
"""Regenerate docs/parse.png and docs/normalize.png from real urlkit output.

Run: python tools/make_shots.py   (requires Pillow)
Uses the same renderers the CLI prints with, colors forced on, fully offline.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "tools"))
import urlkit as uk
import render_terminal as rt

PARSE_URL = "https://user:pass@Example.COM:8443/a/b?q=hello%20world&lang=en#docs"
NORMALIZE_URL = "HTTP://Example.COM:80/a/./b/../c?greeting=hello world&lang=en#"


def render(name, ansi, cmd, title):
    rt.render(rt.parse_ansi(ansi), title, cmd, os.path.join(ROOT, "docs", name + ".png"))


def main():
    os.makedirs(os.path.join(ROOT, "docs"), exist_ok=True)
    render("parse", uk.render_parse(uk.parse_url(PARSE_URL), True),
           'python urlkit.py parse "%s"' % PARSE_URL, "urlkit — parse")
    render("normalize", uk.render_url(uk.normalize_url(NORMALIZE_URL), True),
           'python urlkit.py normalize "%s"' % NORMALIZE_URL, "urlkit — normalize")


if __name__ == "__main__":
    main()
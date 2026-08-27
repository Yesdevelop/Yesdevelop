"""Build catalog.js for the local reader from existing markdown files."""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ("answers", "articles", "ideas")
ID_RE = re.compile(r"^(\d{3})-")
FM_RE = re.compile(r"^---\n(.*?)\n---\n*", re.S)


def parse_frontmatter(raw: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        val = val.strip()
        if val.startswith('"') and val.endswith('"'):
            val = json.loads(val)
        meta[key.strip()] = val
    return meta


def parse_md(path: Path) -> dict | None:
    text = path.read_text(encoding="utf-8")
    rel = path.relative_to(ROOT).as_posix()
    m = ID_RE.match(path.name)
    if not m:
        return None
    fm_m = FM_RE.match(text)
    meta = parse_frontmatter(fm_m.group(1)) if fm_m else {}
    body = text[fm_m.end() :] if fm_m else text
    body = body.strip()
    title = meta.get("title") or path.stem
    date = meta.get("date") or ""
    if date in {"null", "None"}:
        date = ""
    votes = meta.get("votes")
    vote_n = None
    if votes not in (None, "", "null", "None"):
        try:
            vote_n = int(float(votes))
        except ValueError:
            vote_n = None
    year = date[:4] if date[:4].isdigit() else "未知"
    return {
        "id": m.group(1),
        "file": rel,
        "title": title,
        "type": meta.get("type") or "回答",
        "date": date,
        "votes": vote_n,
        "year": year,
        "md": body,
    }


def write_catalog_js(root: Path = ROOT) -> Path:
    items: list[dict] = []
    for folder in FOLDERS:
        for path in sorted((root / folder).glob("*.md")):
            item = parse_md(path)
            if item:
                items.append(item)
    items.sort(key=lambda x: x["id"])
    out = root / "catalog.js"
    payload = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
    out.write_text(f"window.ZHUCI_CATALOG={payload};\n", encoding="utf-8")
    return out


if __name__ == "__main__":
    path = write_catalog_js()
    print(path, path.stat().st_size)
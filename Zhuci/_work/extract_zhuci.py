"""Extract Zhihu answers from 朱慈.docx into markdown files."""

from __future__ import annotations

import json
import re
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

DOCX = Path(r"C:\Users\Yeshui\Downloads\朱慈.docx")
ROOT = Path(__file__).resolve().parents[1]
ANSWERS = ROOT / "answers"
ARTICLES = ROOT / "articles"
IDEAS = ROOT / "ideas"
IMAGES = ROOT / "images"
WORK = ROOT / "_work"

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
W = f"{{{W_NS}}}"
NS = {"w": W_NS}

DATE_RE = re.compile(r"^(发布于|编辑于)\s+(\d{4}-\d{2}-\d{2})(?:\s+(\d{2}:\d{2}))?")
AUTHOR_LINE_RE = re.compile(r"^作者：朱慈\s*链接：(.*?)\s*来源：知乎")
AGREE_RE = re.compile(
    r"(?:(\S+)\s+等\s+)?(\d+(?:\.\d+)?)\s*(万)?人?赞同了该(回答|文章|想法)"
)
AGREE_SHORT_RE = re.compile(r"^赞同\s+([\d.]+)\s*(万)?$")
AGREE_WAN_RE = re.compile(r"^([\d.]+)\s*万人赞同了该(回答|文章|想法)")
BIO_RE = re.compile(r"^精神病纪录片")
ZHIHU_URL_RE = re.compile(r"https?://[^\s]+")
ILLEGAL_FN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')

CHROME_EXACT = {
    "朱慈",
    "精神病纪录片进度99.981%",
    "置顶",
    "关注者",
}
YIZAN_RE = re.compile(r"^已赞同\s*")
HEADINGS = {"heading 1", "heading 2"}

# Repeated profile avatars, not answer content.
SKIP_MEDIA = {"media/image1.jpeg", "media/image2.png"}


class Para:
    __slots__ = ("i", "style", "text", "media", "hrefs")

    def __init__(self, i: int, style: str | None, text: str, media: list[str], hrefs: list[str]):
        self.i = i
        self.style = style
        self.text = text
        self.media = media
        self.hrefs = hrefs

    @property
    def nonempty(self) -> bool:
        return bool(self.text) or bool(self.content_media)


    @property
    def content_media(self) -> list[str]:
        return [m for m in self.media if m not in SKIP_MEDIA]


def load_paras(docx: Path) -> list[Para]:
    with zipfile.ZipFile(docx) as z:
        root = ET.fromstring(z.read("word/document.xml"))
        styles_root = ET.fromstring(z.read("word/styles.xml"))
        rels_root = ET.fromstring(z.read("word/_rels/document.xml.rels"))

    style_names: dict[str, str] = {}
    for s in styles_root.findall(".//w:style", NS):
        sid = s.get(f"{W}styleId")
        name_el = s.find("w:name", NS)
        name = name_el.get(f"{W}val") if name_el is not None else sid
        if sid:
            style_names[sid] = name or sid

    relmap: dict[str, str] = {}
    for rel in rels_root:
        rid = rel.get("Id")
        tgt = rel.get("Target")
        if rid and tgt:
            relmap[rid] = tgt

    paras: list[Para] = []
    for i, p in enumerate(root.findall(".//w:p", NS)):
        ppr = p.find("w:pPr", NS)
        sid = None
        if ppr is not None:
            ps = ppr.find("w:pStyle", NS)
            if ps is not None:
                sid = ps.get(f"{W}val")
        texts: list[str] = []
        for t in p.findall(".//w:t", NS):
            if t.text:
                texts.append(t.text)
            if t.tail:
                texts.append(t.tail)
        text = "".join(texts).replace("\u200b", "").strip()
        media: list[str] = []
        hrefs: list[str] = []
        for el in p.iter():
            if el.tag.endswith("}blip"):
                embed = el.get(f"{{{R_NS}}}embed")
                if embed and embed in relmap:
                    media.append(relmap[embed])
            if el.tag.endswith("}hyperlink"):
                rid = el.get(f"{{{R_NS}}}id")
                if rid and rid in relmap:
                    hrefs.append(relmap[rid])
        paras.append(Para(i, style_names.get(sid, sid), text, media, hrefs))
    return paras


def is_date(text: str) -> bool:
    return bool(DATE_RE.match(text))


def is_bio(text: str) -> bool:
    return bool(BIO_RE.match(text))


def is_agree_line(text: str) -> bool:
    return bool(AGREE_RE.search(text) or AGREE_SHORT_RE.match(text) or AGREE_WAN_RE.match(text))


def is_author_line(text: str) -> bool:
    return bool(AUTHOR_LINE_RE.match(text))


def is_chrome(text: str) -> bool:
    if not text:
        return True
    if text in CHROME_EXACT or is_bio(text):
        return True
    if is_date(text) or is_agree_line(text) or is_author_line(text):
        return True
    if YIZAN_RE.match(text):
        return True
    return False


def looks_like_title(text: str) -> bool:
    if not text or is_chrome(text):
        return False
    return text.endswith(("？", "?")) and 2 <= len(text) <= 200


def idea_title(body: list[str], pinned: bool) -> str:
    if pinned:
        return "置顶说明"
    text = next((b for b in body if b and not b.startswith("![](")), "")
    if not text:
        return "想法"
    for sep in ("。", "！", "？", "\n", "，"):
        if sep in text:
            cand = text.split(sep, 1)[0].strip()
            if 4 <= len(cand) <= 36:
                return cand
    return text[:32] + ("…" if len(text) > 32 else "")


def extract_preamble(paras: list[Para], floor: int, header_i: int) -> tuple[str | None, str | None, list[str]]:
    """Title and optional asker description sitting immediately before an author card."""
    cluster: list[Para] = []
    i = header_i - 1
    while i >= floor:
        p = paras[i]
        if is_date(p.text) or p.text == "朱慈" or is_bio(p.text):
            break
        if not p.text or is_chrome(p.text):
            i -= 1
            continue
        cluster.append(p)
        if p.style in HEADINGS:
            break
        if looks_like_title(p.text):
            found_heading = False
            for peek in range(i - 1, max(floor - 1, i - 12), -1):
                q = paras[peek]
                if is_date(q.text) or q.text == "朱慈":
                    break
                if q.style in HEADINGS:
                    found_heading = True
                    break
            if found_heading:
                i -= 1
                continue
            break
        if len(cluster) == 1 and p.text.endswith(("。", "！", "!")):
            found_title = False
            for peek in range(i - 1, max(floor - 1, i - 25), -1):
                q = paras[peek]
                if is_date(q.text) or q.text == "朱慈":
                    break
                if q.style in HEADINGS or looks_like_title(q.text):
                    found_title = True
                    break
            if not found_title:
                return None, None, []
        if len(cluster) > 20:
            cluster = []
            break
        i -= 1
    cluster.reverse()
    if not cluster:
        return None, None, []

    headings = [p for p in cluster if p.style in HEADINGS]
    if headings:
        title_p = headings[0]
        desc = [p.text for p in cluster if p.i > title_p.i and p.text]
        return title_p.text, title_p.style, desc

    if looks_like_title(cluster[0].text):
        return cluster[0].text, cluster[0].style, [p.text for p in cluster[1:]]
    # Previous-answer leakage, not a title.
    return None, None, []


def parse_agree(text: str) -> tuple[int | None, str | None]:
    m = AGREE_RE.search(text)
    if m:
        n = float(m.group(2))
        if m.group(3):
            n *= 10000
        return int(n), m.group(4)
    m = AGREE_WAN_RE.match(text)
    if m:
        return int(float(m.group(1)) * 10000), m.group(2)
    m = AGREE_SHORT_RE.match(text)
    if m:
        n = float(m.group(1))
        if m.group(2):
            n *= 10000
        return int(n), None
    return None, None


def parse_date(text: str) -> tuple[str, str, str]:
    m = DATE_RE.match(text)
    if not m:
        return "", "", ""
    kind, day, hm = m.group(1), m.group(2), m.group(3) or ""
    return kind, day, f"{day} {hm}".strip()


def extract_url(text: str) -> str:
    m = AUTHOR_LINE_RE.match(text)
    if m:
        return m.group(1).strip()
    m = ZHIHU_URL_RE.search(text)
    return m.group(0).rstrip(")。,，") if m else ""


def find_author_headers(paras: list[Para]) -> list[int]:
    headers: list[int] = []
    n = len(paras)
    for i, p in enumerate(paras):
        if p.text != "朱慈":
            continue
        found_bio = False
        for j in range(i + 1, min(i + 8, n)):
            t = paras[j].text
            if not t:
                continue
            if is_bio(t):
                found_bio = True
                break
            if t == "朱慈" or t in CHROME_EXACT or is_agree_line(t):
                continue
            break
        if found_bio:
            headers.append(i)
    return headers


def collect_body(block: list[Para], skip_texts: set[str] | None = None) -> tuple[list[str], list[str], str]:
    skip_texts = skip_texts or set()
    lines: list[str] = []
    media: list[str] = []
    url = ""
    for p in block:
        if p.text in skip_texts:
            continue
        if is_author_line(p.text):
            url = url or extract_url(p.text)
            continue
        if p.content_media:
            media.extend(p.content_media)
            for m in p.content_media:
                name = Path(m).name
                lines.append(f"![](../images/{name})")
        if is_date(p.text) or is_chrome(p.text) or is_bio(p.text):
            continue
        if p.text:
            if not url:
                maybe = extract_url(p.text)
                if maybe and p.text.strip() == maybe:
                    url = maybe
                    continue
            lines.append(p.text)
    return lines, media, url


def first_agree(block: list[Para]) -> str:
    for p in block:
        if is_agree_line(p.text) and parse_agree(p.text)[1]:
            return p.text
    return ""


def build_entries(paras: list[Para]) -> list[dict]:
    headers = find_author_headers(paras)
    dates = [p.i for p in paras if is_date(p.text)]
    content_headers = headers[1:] if headers else []

    segments: list[tuple[int, int]] = []
    prev = 0
    for di in dates:
        segments.append((prev, di))
        prev = di + 1

    entries: list[dict] = []
    pinned_used = False

    def add_entry(title: str | None, heading: str | None, desc: list[str], body: list[str],
                  media: list[str], url: str, date_para: Para | None,
                  agree_text: str, start: int, end: int):
        nonlocal pinned_used
        kind, day, when = parse_date(date_para.text) if date_para else ("", "", "")
        votes, ptype = parse_agree(agree_text) if agree_text else (None, None)
        if not ptype:
            if heading == "heading 2" or (title or "").startswith("病友日记"):
                ptype = "文章"
            elif heading == "heading 1" or looks_like_title(title or ""):
                ptype = "回答"
            elif not title:
                ptype = "想法"
            else:
                ptype = "回答"

        if ptype == "想法":
            nearby_pin = any(p.text == "置顶" for p in paras[max(0, start - 8): start + 8])
            pinned = (not pinned_used) and (nearby_pin or start < 20)
            if pinned:
                pinned_used = True
            title = idea_title(body, pinned)
        elif not title:
            title = idea_title(body, False) if body else "无标题"

        # Untitled 想法 exported as one long paragraph (no question, no 赞同了该X).
        if ptype == "回答" and not agree_text and title and len(title) > 80 and not desc:
            body = [title] + (body or [])
            title = idea_title(body, False)
            ptype = "想法"

        entries.append({
            "title": title,
            "type": ptype,
            "heading": heading,
            "date_kind": kind,
            "date": day,
            "datetime": when,
            "votes": votes,
            "url": url,
            "question": desc,
            "body": body,
            "media": media,
            "start": start,
            "end": end,
        })

    for seg_start, date_i in segments:
        date_para = paras[date_i]
        headers_in = [h for h in content_headers if seg_start <= h < date_i]
        if seg_start == 0 and headers and headers[0] < date_i and headers[0] not in headers_in:
            headers_in = [headers[0]] + headers_in

        if not headers_in:
            block = paras[seg_start:date_i]
            useful = [p for p in block if p.text and not is_chrome(p.text)]
            headings = [p for p in useful if p.style in HEADINGS]
            agree_text = first_agree(block)
            url = ""
            for p in block:
                if is_author_line(p.text):
                    url = extract_url(p.text)
            if headings:
                title_p = headings[0]
                desc = [p.text for p in useful if p.i > title_p.i]
                body, media, url2 = collect_body(block, skip_texts={title_p.text, *desc})
                add_entry(title_p.text, title_p.style, desc, body, media, url or url2,
                          date_para, agree_text, seg_start, date_i)
            elif useful and looks_like_title(useful[0].text):
                title = useful[0].text
                body, media, url2 = collect_body(block, skip_texts={title})
                add_entry(title, useful[0].style, [], body, media, url or url2,
                          date_para, agree_text, seg_start, date_i)
            else:
                body, media, url2 = collect_body(block)
                add_entry(None, None, [], body, media, url or url2,
                          date_para, agree_text, seg_start, date_i)
            continue

        bounds = headers_in + [date_i]
        for idx, h in enumerate(headers_in):
            floor = seg_start if idx == 0 else headers_in[idx - 1]
            title, heading, desc = extract_preamble(paras, floor, h)
            end = bounds[idx + 1]
            post = paras[h:end]
            agree_text = first_agree(post)
            body, media, url = collect_body(post)
            own_date = date_para if idx == len(headers_in) - 1 else None
            add_entry(title, heading, desc, body, media, url, own_date, agree_text, h, end)

    return entries


def sanitize_filename(title: str, max_len: int = 48) -> str:
    t = ILLEGAL_FN.sub("", title)
    t = t.replace("？", "").replace("?", "")
    t = re.sub(r"\s+", "-", t.strip())
    t = t.strip(".-") or "untitled"
    return t[:max_len]


def yaml_escape(s: str) -> str:
    s = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def to_markdown(entry: dict) -> str:
    fm = [
        "---",
        f"title: {yaml_escape(entry['title'])}",
        f"type: {entry['type']}",
        f"date: {yaml_escape(entry['datetime']) if entry['datetime'] else 'null'}",
        f"date_kind: {entry['date_kind'] or '未知'}",
        f"votes: {entry['votes'] if entry['votes'] is not None else 'null'}",
        f"source: zhihu",
        f"author: 朱慈",
    ]
    if entry.get("url"):
        fm.append(f"zhihu_url: {yaml_escape(entry['url'])}")
    fm.append("---")
    parts = ["\n".join(fm), "", f"# {entry['title']}", ""]
    if entry.get("question"):
        parts.append("## 问题描述")
        parts.append("")
        for q in entry["question"]:
            for line in q.splitlines() or [q]:
                parts.append(f"> {line}")
            parts.append(">")
        if parts[-1] == ">":
            parts.pop()
        parts.append("")
        parts.append("## 回答")
        parts.append("")
    body = entry.get("body") or []
    # collapse accidental leading chrome leftovers
    cleaned = []
    for line in body:
        if is_chrome(line):
            continue
        cleaned.append(line)
    parts.append("\n\n".join(cleaned).strip())
    parts.append("")
    return "\n".join(parts).rstrip() + "\n"


def dest_dir(entry: dict) -> Path:
    return {"回答": ANSWERS, "文章": ARTICLES, "想法": IDEAS}.get(entry["type"], ANSWERS)


def write_outputs(paras: list[Para], entries: list[dict]) -> dict:
    for d in (ANSWERS, ARTICLES, IDEAS, IMAGES, WORK):
        d.mkdir(parents=True, exist_ok=True)
    for d in (ANSWERS, ARTICLES, IDEAS):
        for old in d.glob("*.md"):
            old.unlink()

    # extract content images
    with zipfile.ZipFile(DOCX) as z:
        for name in z.namelist():
            if not name.startswith("word/media/") or name.endswith("/"):
                continue
            raw_name = Path(name).name
            if raw_name in {"image1.jpeg", "image2.png"}:
                continue
            (IMAGES / raw_name).write_bytes(z.read(name))

    used_names: dict[str, int] = {}
    written = []
    for i, e in enumerate(entries, 1):
        date = e["date"] or "undated"
        slug = sanitize_filename(e["title"])
        fname = f"{i:03d}-{date}-{slug}.md"
        if fname in used_names:
            used_names[fname] += 1
            fname = f"{i:03d}-{date}-{slug}-{used_names[fname]}.md"
        else:
            used_names[fname] = 1
        path = dest_dir(e) / fname
        path.write_text(to_markdown(e), encoding="utf-8")
        e["file"] = str(path.relative_to(ROOT)).replace("\\", "/")
        written.append(e["file"])

    catalog = []
    for e in entries:
        catalog.append({
            "file": e["file"],
            "title": e["title"],
            "type": e["type"],
            "date": e["datetime"],
            "votes": e["votes"],
            "url": e.get("url") or "",
            "body_paras": len(e.get("body") or []),
            "question_paras": len(e.get("question") or []),
            "start": e["start"],
            "end": e["end"],
            "heading": e.get("heading"),
        })
    (WORK / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    anomalies = []
    titles = Counter(e["title"] for e in entries)
    for e in entries:
        reasons = []
        if not e["title"] or e["title"] == "无标题":
            reasons.append("missing_title")
        if not e.get("body"):
            reasons.append("empty_body")
        elif len(e["body"]) <= 1 and sum(len(x) for x in e["body"]) < 40:
            reasons.append("very_short_body")
        if not e.get("date"):
            reasons.append("missing_date")
        if e["title"] in titles and titles[e["title"]] > 1:
            reasons.append("duplicate_title")
        if reasons:
            anomalies.append({"file": e["file"], "title": e["title"], "reasons": reasons})
    (WORK / "anomalies.json").write_text(
        json.dumps(anomalies, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    type_count = Counter(e["type"] for e in entries)
    years: dict[str, list[dict]] = {}
    for e in entries:
        y = (e["date"] or "未知")[:4]
        years.setdefault(y, []).append(e)

    readme = [
        "# 朱慈",
        "",
        "从知乎用户「朱慈」导出的 Word 文档整理而来的问答与文章。",
        "",
        f"- 来源文件：`朱慈.docx`",
        f"- 条目总数：**{len(entries)}**",
        f"- 回答：{type_count.get('回答', 0)}",
        f"- 文章：{type_count.get('文章', 0)}",
        f"- 想法：{type_count.get('想法', 0)}",
        "",
        "每篇一份 Markdown，按类型放在 `answers/`、`articles/`、`ideas/`。",
        "阅读器：打开 `index.html`。正文里的内容图片在 `images/`；头像等页面装饰未收录。",
        "",
        "重新提取：`python _work/extract_zhuci.py`（读取 `C:/Users/Yeshui/Downloads/朱慈.docx`）。",
        "原文有两篇回答未带发布时间，文件名里为 `undated`。",
        "",
        "## 目录",
        "",
    ]
    for y in sorted(years):
        readme.append(f"### {y}")
        readme.append("")
        for e in years[y]:
            votes = f" · {e['votes']} 赞" if e.get("votes") is not None else ""
            when = e["datetime"] or "日期未知"
            readme.append(f"- [{e['title']}]({e['file']}) · {when} · {e['type']}{votes}")
        readme.append("")
    (ROOT / "README.md").write_text("\n".join(readme), encoding="utf-8")

    import sys

    if str(WORK) not in sys.path:
        sys.path.insert(0, str(WORK))
    from build_catalog_js import write_catalog_js

    write_catalog_js(ROOT)

    return {
        "entries": len(entries),
        "types": dict(type_count),
        "anomalies": len(anomalies),
        "files": written,
    }


def main() -> None:
    paras = load_paras(DOCX)
    entries = build_entries(paras)
    stats = write_outputs(paras, entries)
    print(json.dumps({k: v for k, v in stats.items() if k != "files"}, ensure_ascii=False, indent=2))
    print("headers", len(find_author_headers(paras)))
    print("anomalies", stats["anomalies"])


if __name__ == "__main__":
    main()

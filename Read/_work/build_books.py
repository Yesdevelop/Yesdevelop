#!/usr/bin/env python3
"""Parse public-domain English texts, align Madame Bovary with the local
Chinese edition by chapter, then write reader data files and EPUB sources."""

from __future__ import annotations

import json
import math
import re
import zipfile
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = Path(__file__).resolve().parent
BOOKS = ROOT / "books"
ZH_TEXT = WORK / "bovary-zh" / "OEBPS" / "Text"

CN_NUM = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
    "十一": 11,
    "十二": 12,
    "十三": 13,
    "十四": 14,
    "十五": 15,
}

EN_CHAP = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
}

ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V", 6: "VI", 7: "VII", 8: "VIII", 9: "IX"}

NAME_PAIRS = [
    ("charles", "查理"),
    ("bovary", "包法利"),
    ("emma", "爱玛"),
    ("homais", "郝麦"),
    ("rodolphe", "罗道耳弗"),
    ("léon", "赖昂"),
    ("leon", "赖昂"),
    ("berthe", "贝尔特"),
    ("rouen", "鲁昂"),
    ("yonville", "永镇"),
    ("tostes", "道特"),
    ("rouault", "卢欧"),
    ("lheureux", "勒乐"),
    ("bournisien", "布尔尼贤"),
    ("hippolyte", "伊波利特"),
    ("justin", "朱斯丹"),
    ("vaubyessard", "渥毕萨尔"),
    ("dupuis", "迪皮伊"),
    ("lefrancois", "勒弗朗索瓦"),
    ("lefrançois", "勒弗朗索瓦"),
    ("binet", "比内"),
    ("hivert", "伊维尔"),
    ("felicite", "费莉西"),
    ("félicité", "费莉西"),
    ("lestiboudois", "勒斯蒂布杜瓦"),
    ("guillaumin", "吉约曼"),
    ("canivet", "卡尼韦"),
    ("lariviere", "拉里维耶尔"),
    ("larivière", "拉里维耶尔"),
    ("charbovari", "查包法芮"),
    ("roger", "罗杰"),
    ("gatsby", "盖茨比"),
    ("nick", "尼克"),
    ("daisy", "黛熙"),
    ("buchanan", "布坎南"),
    ("jordan", "乔丹"),
    ("baker", "贝克"),
    ("myrtle", "茉特尔"),
    ("wilson", "威尔逊"),
    ("carraway", "卡拉威"),
    ("wolfsheim", "沃尔夫山姆"),
    ("meyer", "迈耶"),
    ("klipspringer", "克利普斯普林格"),
    ("cody", "科迪"),
    ("west egg", "西卵"),
    ("east egg", "东卵"),
    ("new haven", "纽黑文"),
    ("louisville", "路易斯维尔"),
]

ABBREV = {
    "mr", "mrs", "ms", "miss", "dr", "prof", "sr", "jr", "st", "vs", "etc",
    "no", "vol", "ch", "mme", "mlle", "messrs", "gen", "col", "capt", "rev",
    "hon", "mt", "jan", "feb", "mar", "apr", "jun", "jul", "aug", "sep",
    "sept", "oct", "nov", "dec", "chap",
}


def collapse(text: str) -> str:
    text = unescape(text).replace("\xa0", " ").replace("\u3000", " ")
    return re.sub(r"\s+", " ", text).strip()


def strip_tags(html: str) -> str:
    html = re.sub(r"<aside\b[^>]*>.*?</aside>", "", html, flags=re.S | re.I)
    html = re.sub(r"<sup\b[^>]*>.*?</sup>", "", html, flags=re.S | re.I)
    html = re.sub(r"<img\b[^>]*/?>", "", html, flags=re.I)
    html = re.sub(r"<[^>]+>", "", html)
    return collapse(html)


def parse_cn_heading(text: str) -> int | None:
    key = re.sub(r"\s+", "", text)
    return CN_NUM.get(key)


def iter_zh_blocks(html: str):
    html = re.sub(r"<aside\b[^>]*>.*?</aside>", "", html, flags=re.S | re.I)
    for match in re.finditer(r"<(h2|p)\b[^>]*>(.*?)</\1>", html, flags=re.S | re.I):
        kind = match.group(1).lower()
        text = strip_tags(match.group(2))
        if text:
            yield kind, text


def parse_bovary_zh() -> dict[tuple[int, int], list[str]]:
    files = [
        (1, "chapter002.xhtml"),
        (2, "chapter003_split_000.xhtml"),
        (2, "chapter003_split_001.xhtml"),
        (3, "chapter004_split_000.xhtml"),
        (3, "chapter004_split_001.xhtml"),
    ]
    chapters: dict[tuple[int, int], list[str]] = {}
    for part, name in files:
        html = (ZH_TEXT / name).read_text(encoding="utf-8")
        current: list[str] | None = None
        for kind, text in iter_zh_blocks(html):
            if kind == "h2":
                num = parse_cn_heading(text)
                if num is None:
                    continue
                current = []
                chapters[(part, num)] = current
                continue
            if current is not None:
                current.append(text)
    return chapters


def parse_bovary_en(md: str) -> dict[tuple[int, int], list[str]]:
    start = md.find("## MADAME BOVARY")
    if start < 0:
        raise RuntimeError("Cannot find Madame Bovary body")
    part = 0
    chap = 0
    chapters: dict[tuple[int, int], list[str]] = {}
    current: list[str] | None = None
    part_re = re.compile(r"^##\s+Part\s+(I{1,3})\.?\s*$", re.I)
    chap_re = re.compile(r"^##\s+Chapter\s+([A-Za-z]+)\s*$", re.I)
    roman = {"i": 1, "ii": 2, "iii": 3}
    for raw in md[start:].splitlines():
        line = raw.strip()
        if not line or line == "---":
            continue
        if line.startswith("*** END OF THE PROJECT GUTENBERG"):
            break
        if re.match(r"^\[\d+\]", line):
            continue
        m_part = part_re.match(line)
        if m_part:
            part = roman[m_part.group(1).lower()]
            current = None
            continue
        m_chap = chap_re.match(line)
        if m_chap:
            chap = EN_CHAP[m_chap.group(1).lower()]
            current = []
            chapters[(part, chap)] = current
            continue
        if line.startswith("#"):
            continue
        if current is None:
            continue
        line = re.sub(r"\[\d+\]", "", line)
        line = collapse(line)
        if line:
            current.append(line)
    return chapters


def parse_html_paras(html: str) -> list[str]:
    html = re.sub(r"<aside\b[^>]*>.*?</aside>", "", html, flags=re.S | re.I)
    html = re.sub(r"<sup\b[^>]*>.*?</sup>", "", html, flags=re.S | re.I)
    paras: list[str] = []
    for match in re.finditer(r"<p\b[^>]*>(.*?)</p>", html, flags=re.S | re.I):
        text = strip_tags(match.group(1))
        if text:
            paras.append(text)
    return paras


def parse_gatsby_zh() -> dict[int | str, list[str]]:
    root = WORK / "gatsby-zh" / "text"
    chapters: dict[int | str, list[str]] = {
        "front": parse_html_paras((root / "part0006.html").read_text(encoding="utf-8"))
    }
    files = {
        1: "part0007.html",
        2: "part0008.html",
        3: "part0009.html",
        4: "part0010.html",
        5: "part0011.html",
        6: "part0012.html",
        7: "part0013.html",
        8: "part0014.html",
        9: "part0015.html",
    }
    for num, name in files.items():
        chapters[num] = parse_html_paras((root / name).read_text(encoding="utf-8"))
    return chapters


def parse_gatsby(md: str) -> list[dict]:
    chap_re = re.compile(r"^##\s+(I{1,3}|IV|V|VI|VII|VIII|IX)\s*$")
    roman_to_n = {v: k for k, v in ROMAN.items()}
    chapters: list[dict] = []
    front: list[dict] = []
    current: list[dict] | None = front
    title = "Dedication"
    body_started = False
    for raw in md.splitlines():
        line = raw.strip()
        if line.startswith("*** START OF THE PROJECT GUTENBERG"):
            continue
        if line.startswith("*** END OF THE PROJECT GUTENBERG"):
            break
        if line.startswith("# ") or line.startswith("The Project Gutenberg"):
            continue
        m = chap_re.match(line)
        if m:
            if current is front and front:
                chapters.append({"id": "front", "title": title, "paragraphs": front})
            n = roman_to_n[m.group(1)]
            title = f"Chapter {m.group(1)}"
            current = []
            chapters.append({"id": f"ch-{n}", "n": n, "title": title, "paragraphs": current})
            body_started = True
            continue
        if not line:
            continue
        if line == "---":
            if body_started and current is not None:
                current.append({"type": "break"})
            continue
        if current is None:
            continue
        current.append({
            "type": "text",
            "en": collapse(line),
            "sentences": [{"en": sent, "zh": "", "scope": "none"} for sent in split_en(collapse(line))],
        })
    return [ch for ch in chapters if ch["paragraphs"]]


def words(text: str) -> int:
    return max(1, len(re.findall(r"[A-Za-z0-9’']+", text)))


def zh_len(text: str) -> int:
    return max(1, len(re.findall(r"[\u4e00-\u9fff0-9A-Za-z]", text)))


def name_overlap(en: str, zh: str) -> int:
    en_l = en.lower()
    score = 0
    for en_name, zh_name in NAME_PAIRS:
        if en_name in en_l and zh_name in zh:
            score += 1
    return score


def is_quote(text: str) -> bool:
    t = text.strip()
    return bool(t) and t[0] in "\"“«「『" and len(t) < 220


def unit_size(text: str, lang: str) -> float:
    return float(words(text) if lang == "en" else zh_len(text))


def split_en(text: str) -> list[str]:
    text = collapse(text)
    if not text:
        return []
    pieces: list[str] = []
    buf: list[str] = []
    i = 0
    while i < len(text):
        ch = text[i]
        buf.append(ch)
        if ch in ".!?…":
            while i + 1 < len(text) and text[i + 1] in ".!?…\"”'’":
                i += 1
                buf.append(text[i])
            rest = text[i + 1 :]
            if not rest.strip():
                pieces.append("".join(buf).strip())
                buf = []
            else:
                word = "".join(buf)
                last = re.findall(r"([A-Za-z]+)\s*$", word[:-1])
                abbrev = last and last[0].lower() in ABBREV
                isolated_initial = bool(re.search(r"\b[A-Z]\s*$", word[:-1]))
                next_ok = re.match(r"\s+[“\"A-Z(]", rest)
                if next_ok and not abbrev and not isolated_initial:
                    pieces.append("".join(buf).strip())
                    buf = []
        i += 1
    tail = "".join(buf).strip()
    if tail:
        pieces.append(tail)
    return [p for p in pieces if p]


def split_zh(text: str) -> list[str]:
    text = collapse(text)
    if not text:
        return []
    parts = re.findall(r"[^。！？…]+[。！？…][」』”’]*|[^。！？…]+$", text)
    return [collapse(p) for p in parts if collapse(p)]


def name_mask(text: str, lang: str) -> int:
    mask = 0
    if lang == "en":
        low = text.lower()
        for i, (en_name, _) in enumerate(NAME_PAIRS):
            if en_name in low:
                mask |= 1 << i
    else:
        for i, (_, zh_name) in enumerate(NAME_PAIRS):
            if zh_name in text:
                mask |= 1 << i
    return mask


def feat(units: list[str], lang: str):
    sizes = [unit_size(u, lang) for u in units]
    names = [name_mask(u, lang) for u in units]
    quotes = [is_quote(u) for u in units]
    prefix = [0.0]
    for size in sizes:
        prefix.append(prefix[-1] + size)
    return sizes, names, quotes, prefix


def pair_score_fast(en_f, zh_f, i: int, j: int, a: int, b: int, ratio: float) -> float:
    en_size = en_f[3][i + a] - en_f[3][i]
    zh_size = zh_f[3][j + b] - zh_f[3][j]
    expected = en_size / ratio
    delta = abs(zh_size - expected) / (expected + 1.0)
    length = math.exp(-3.2 * delta)
    en_names = 0
    zh_names = 0
    en_quote = False
    zh_quote = False
    for k in range(a):
        en_names |= en_f[1][i + k]
        en_quote = en_quote or en_f[2][i + k]
    for k in range(b):
        zh_names |= zh_f[1][j + k]
        zh_quote = zh_quote or zh_f[2][j + k]
    names = (en_names & zh_names).bit_count()
    quote = 0.12 if en_quote == zh_quote and (en_quote or zh_quote) else 0.0
    short_pen = 0.15 if max(a, b) >= 3 else 0.0
    return length + 0.18 * names + quote - short_pen


def align_units(en_units: list[str], zh_units: list[str], ratio: float | None = None):
    if not en_units:
        return []
    if not zh_units:
        return [([i], []) for i in range(len(en_units))]
    en_f = feat(en_units, "en")
    zh_f = feat(zh_units, "zh")
    if ratio is None:
        ratio = en_f[3][-1] / max(1.0, zh_f[3][-1])
    n, m = len(en_units), len(zh_units)
    neg = -1e9
    dp = [[neg] * (m + 1) for _ in range(n + 1)]
    bt: list[list[tuple[int, int] | None]] = [[None] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    beads = [(1, 1), (1, 2), (2, 1), (2, 2), (1, 3), (3, 1), (3, 2), (2, 3)]
    skip = -1.15
    band = max(12, int(0.18 * max(n, m)) + abs(n - m) + 6)
    for i in range(n + 1):
        j_mid = 0 if n == 0 else round(i * m / n)
        j0 = 0 if i == 0 or i == n else max(0, j_mid - band)
        j1 = m if i == 0 or i == n else min(m, j_mid + band)
        for j in range(j0, j1 + 1):
            if dp[i][j] <= neg / 2:
                continue
            if i < n and dp[i][j] + skip > dp[i + 1][j]:
                dp[i + 1][j] = dp[i][j] + skip
                bt[i + 1][j] = (1, 0)
            if j < m and dp[i][j] + skip > dp[i][j + 1]:
                dp[i][j + 1] = dp[i][j] + skip
                bt[i][j + 1] = (0, 1)
            for a, b in beads:
                if i + a <= n and j + b <= m:
                    s = dp[i][j] + pair_score_fast(en_f, zh_f, i, j, a, b, ratio)
                    if s > dp[i + a][j + b]:
                        dp[i + a][j + b] = s
                        bt[i + a][j + b] = (a, b)
    if dp[n][m] <= neg / 2:
        # band missed the end; fall back to full DP on smaller tails
        for i in range(n + 1):
            for j in range(m + 1):
                if dp[i][j] <= neg / 2:
                    continue
                if i < n and dp[i][j] + skip > dp[i + 1][j]:
                    dp[i + 1][j] = dp[i][j] + skip
                    bt[i + 1][j] = (1, 0)
                if j < m and dp[i][j] + skip > dp[i][j + 1]:
                    dp[i][j + 1] = dp[i][j] + skip
                    bt[i][j + 1] = (0, 1)
                for a, b in beads:
                    if i + a <= n and j + b <= m:
                        s = dp[i][j] + pair_score_fast(en_f, zh_f, i, j, a, b, ratio)
                        if s > dp[i + a][j + b]:
                            dp[i + a][j + b] = s
                            bt[i + a][j + b] = (a, b)
    path: list[tuple[list[int], list[int]]] = []
    i, j = n, m
    while i > 0 or j > 0:
        step = bt[i][j]
        if step is None:
            if i:
                path.append(([i - 1], []))
                i -= 1
            elif j:
                path.append(([], [j - 1]))
                j -= 1
            else:
                break
            continue
        a, b = step
        path.append((list(range(i - a, i)) if a else [], list(range(j - b, j)) if b else []))
        i -= a
        j -= b
    path.reverse()
    return path


def attach_sentences(en_paras: list[str], zh_paras: list[str]) -> list[dict]:
    path = align_units(en_paras, zh_paras)
    out = [{"en": p, "sentences": []} for p in en_paras]
    for en_ids, zh_ids in path:
        zh_block = [zh_paras[k] for k in zh_ids]
        zh_sents = [s for p in zh_block for s in split_zh(p)]
        en_sents: list[tuple[int, str]] = []
        for idx in en_ids:
            for sent in split_en(en_paras[idx]):
                en_sents.append((idx, sent))
        if not en_sents:
            continue
        if not zh_sents:
            for idx, sent in en_sents:
                out[idx]["sentences"].append({"en": sent, "zh": "\n".join(zh_block), "scope": "block"})
            continue
        sent_path = align_units([s for _, s in en_sents], zh_sents)
        cursor = 0
        mapped = [s for _, s in en_sents]
        for e_ids, z_ids in sent_path:
            zh_text = "".join(zh_sents[k] for k in z_ids)
            scope = "sentence"
            if len(e_ids) != 1 or len(z_ids) != 1:
                # still usable if the bead is tight
                if len(e_ids) > 1 and z_ids:
                    scope = "group"
                elif not z_ids:
                    zh_text = "\n".join(zh_block)
                    scope = "block"
            for e_i in e_ids:
                para_i, sent = en_sents[e_i]
                out[para_i]["sentences"].append({"en": sent, "zh": zh_text, "scope": scope})
            cursor += len(e_ids)
        # keep original sentence order inside each paragraph
        _ = mapped, cursor
    for para in out:
        if not para["sentences"]:
            para["sentences"] = [{"en": s, "zh": "", "scope": "none"} for s in split_en(para["en"])]
    return out


def chapter_title(part: int, num: int) -> str:
    return f"Part {ROMAN[part]} · Chapter {num}"


def build_bovary():
    en = parse_bovary_en((WORK / "bovary-en.md").read_text(encoding="utf-8"))
    zh = parse_bovary_zh()
    expected = [(1, n) for n in range(1, 10)] + [(2, n) for n in range(1, 16)] + [(3, n) for n in range(1, 12)]
    missing_en = [k for k in expected if k not in en]
    missing_zh = [k for k in expected if k not in zh]
    if missing_en or missing_zh:
        raise RuntimeError(f"Missing chapters en={missing_en} zh={missing_zh}")

    report = []
    chapters = []
    for part, num in expected:
        en_paras = en[(part, num)]
        zh_paras = zh[(part, num)]
        print(f"align {part}.{num} en={len(en_paras)} zh={len(zh_paras)}", flush=True)
        paras = attach_sentences(en_paras, zh_paras)
        path = align_units(en_paras, zh_paras)
        kinds: dict[str, int] = {}
        for a, b in path:
            kinds[f"{len(a)}-{len(b)}"] = kinds.get(f"{len(a)}-{len(b)}", 0) + 1
        report.append(
            {
                "chapter": f"{part}.{num}",
                "en": len(en_paras),
                "zh": len(zh_paras),
                "beads": kinds,
            }
        )
        chapters.append(
            {
                "id": f"{part}-{num}",
                "part": part,
                "n": num,
                "title": chapter_title(part, num),
                "titleZh": f"{'上中下'[part - 1]}卷 · {num}",
                "paragraphs": paras,
            }
        )

    book = {
        "id": "madame-bovary",
        "title": "Madame Bovary",
        "titleZh": "包法利夫人",
        "author": "Gustave Flaubert",
        "translatorEn": "Eleanor Marx-Aveling",
        "translatorZh": "李健吾",
        "sourceEn": "Project Gutenberg #2413",
        "hasZh": True,
        "chapters": chapters,
    }
    return book, report


def weave_aligned(original: list[dict], aligned: list[dict]) -> list[dict]:
    out: list[dict] = []
    i = 0
    for para in original:
        if para.get("type") == "break":
            out.append({"type": "break"})
            continue
        item = aligned[i]
        item["type"] = "text"
        out.append(item)
        i += 1
    return out


def build_gatsby():
    raw = parse_gatsby((WORK / "gatsby-en.md").read_text(encoding="utf-8"))
    zh = parse_gatsby_zh()
    report = []
    chapters = []
    for ch in raw:
        n = ch.get("n")
        key: int | str = n if n is not None else "front"
        en_texts = [p["en"] for p in ch["paragraphs"] if p.get("type") != "break"]
        zh_paras = zh.get(key, [])
        print(f"align gatsby {key} en={len(en_texts)} zh={len(zh_paras)}", flush=True)
        aligned = attach_sentences(en_texts, zh_paras) if zh_paras else [
            {"en": t, "sentences": [{"en": s, "zh": "", "scope": "none"} for s in split_en(t)]}
            for t in en_texts
        ]
        path = align_units(en_texts, zh_paras) if zh_paras else []
        kinds: dict[str, int] = {}
        for a, b in path:
            kinds[f"{len(a)}-{len(b)}"] = kinds.get(f"{len(a)}-{len(b)}", 0) + 1
        report.append({"chapter": str(key), "en": len(en_texts), "zh": len(zh_paras), "beads": kinds})
        chapters.append(
            {
                "id": ch["id"],
                "n": n,
                "title": ch["title"],
                "titleZh": None if n is None else f"第{list(CN_NUM)[n - 1]}章" if n < 10 else None,
                "paragraphs": weave_aligned(ch["paragraphs"], aligned),
            }
        )
    return {
        "id": "the-great-gatsby",
        "title": "The Great Gatsby",
        "titleZh": "了不起的盖茨比",
        "author": "F. Scott Fitzgerald",
        "translatorZh": "李继宏",
        "sourceEn": "Project Gutenberg #64317",
        "hasZh": True,
        "chapters": chapters,
    }, report


def write_js(path: Path, data: dict):
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    path.write_text(
        f"window.READ_BOOKS=window.READ_BOOKS||{{}};window.READ_BOOKS[{json.dumps(data['id'])}]={payload};\n",
        encoding="utf-8",
    )


def write_catalog():
    catalog = [
        {
            "id": "the-great-gatsby",
            "title": "The Great Gatsby",
            "titleZh": "了不起的盖茨比",
            "author": "F. Scott Fitzgerald",
            "translatorZh": "李继宏",
            "hasZh": True,
            "note": "英文为公版原文；中文为你提供的李继宏译本。",
        },
        {
            "id": "madame-bovary",
            "title": "Madame Bovary",
            "titleZh": "包法利夫人",
            "author": "Gustave Flaubert",
            "translatorZh": "李健吾",
            "hasZh": True,
            "note": "英文为公版马克思–艾威林译本；中文为你提供的李健吾译本。",
        },
    ]
    (BOOKS / "catalog.js").write_text(
        "window.READ_CATALOG=" + json.dumps(catalog, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )


def txt_to_paragraphs(text: str) -> list[str]:
    start = re.search(r"\*\*\* START OF.*?\*\*\*", text)
    end = re.search(r"\*\*\* END OF THE PROJECT GUTENBERG", text)
    body = text[start.end() if start else 0 : end.start() if end else None]
    body = body.replace("\r\n", "\n")
    chunks = re.split(r"\n\s*\n", body)
    paras = []
    for chunk in chunks:
        line = collapse(chunk.replace("\n", " "))
        if line:
            paras.append(line)
    return paras


def write_epub(path: Path, title: str, author: str, paragraphs: list[str], extra: str = ""):
    style = (
        "body{font-family:Georgia,serif;line-height:1.6;margin:1.2em;}"
        "h1{font-size:1.4em;}p{margin:0 0 0.9em;text-indent:1.2em;}"
        "p.noindent{text-indent:0;}"
    )
    html_paras = []
    for i, para in enumerate(paragraphs):
        cls = ' class="noindent"' if i == 0 else ""
        esc = (
            para.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        html_paras.append(f"<p{cls}>{esc}</p>")
    chapter = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<html xmlns="http://www.w3.org/1999/xhtml">'
        f"<head><title>{title}</title>"
        '<link rel="stylesheet" href="style.css" type="text/css"/>'
        "</head><body>"
        f"<h1>{title}</h1>"
        f"<p class='noindent'><em>{author}</em></p>"
        f"{'<p class="noindent">' + extra + '</p>' if extra else ''}"
        + "".join(html_paras)
        + "</body></html>"
    )
    opf = f"""<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="bookid" version="2.0">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{title}</dc:title>
    <dc:creator>{author}</dc:creator>
    <dc:language>en</dc:language>
    <dc:identifier id="bookid">urn:read:{path.stem}</dc:identifier>
    <dc:rights>Public domain in the United States. Source: Project Gutenberg.</dc:rights>
  </metadata>
  <manifest>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
    <item id="css" href="style.css" media-type="text/css"/>
    <item id="chap" href="chapter.xhtml" media-type="application/xhtml+xml"/>
  </manifest>
  <spine toc="ncx"><itemref idref="chap"/></spine>
</package>
"""
    ncx = f"""<?xml version="1.0" encoding="utf-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head><meta name="dtb:uid" content="urn:read:{path.stem}"/></head>
  <docTitle><text>{title}</text></docTitle>
  <navMap>
    <navPoint id="n1" playOrder="1"><navLabel><text>{title}</text></navLabel><content src="chapter.xhtml"/></navPoint>
  </navMap>
</ncx>
"""
    container = """<?xml version="1.0" encoding="utf-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles>
</container>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        zf.writestr("META-INF/container.xml", container)
        zf.writestr("OEBPS/content.opf", opf)
        zf.writestr("OEBPS/toc.ncx", ncx)
        zf.writestr("OEBPS/style.css", style)
        zf.writestr("OEBPS/chapter.xhtml", chapter)


def main():
    BOOKS.mkdir(parents=True, exist_ok=True)
    bovary, report = build_bovary()
    gatsby, gatsby_report = build_gatsby()
    write_js(BOOKS / "madame-bovary.data.js", bovary)
    write_js(BOOKS / "the-great-gatsby.data.js", gatsby)
    write_catalog()

    gatsby_txt = (BOOKS / "the-great-gatsby" / "the-great-gatsby.txt").read_text(encoding="utf-8")
    bovary_txt = (BOOKS / "madame-bovary" / "madame-bovary.txt").read_text(encoding="utf-8")
    write_epub(
        BOOKS / "the-great-gatsby" / "the-great-gatsby.epub",
        "The Great Gatsby",
        "F. Scott Fitzgerald",
        txt_to_paragraphs(gatsby_txt),
        extra="Public domain. Source: Project Gutenberg #64317.",
    )
    write_epub(
        BOOKS / "madame-bovary" / "madame-bovary.epub",
        "Madame Bovary",
        "Gustave Flaubert · tr. Eleanor Marx-Aveling",
        txt_to_paragraphs(bovary_txt),
        extra="Public domain. Source: Project Gutenberg #2413.",
    )

    (WORK / "align-report.json").write_text(
        json.dumps({"bovary": report, "gatsby": gatsby_report}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print("chapters", len(bovary["chapters"]), "gatsby", len(gatsby["chapters"]))
    for row in report:
        print(f"{row['chapter']:>5}  en={row['en']:>3} zh={row['zh']:>3}  {row['beads']}")
    print("--- gatsby ---")
    for row in gatsby_report:
        print(f"{row['chapter']:>5}  en={row['en']:>3} zh={row['zh']:>3}  {row['beads']}")


if __name__ == "__main__":
    main()

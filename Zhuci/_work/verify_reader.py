import subprocess
from pathlib import Path

out = Path(r"C:\Users\Yeshui\AppData\Local\Temp\zhuci-dom.html")
edge = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
def dump(url: str) -> str:
    p = subprocess.run(
        [edge, "--headless=new", "--disable-gpu", "--virtual-time-budget=8000",
         "--dump-dom", url],
        capture_output=True,
    )
    return p.stdout.decode("utf-8", "replace")

t = dump("http://127.0.0.1:8765/index.html")
print("list", "317 篇" in t, "置顶说明" in t)
art = dump("http://127.0.0.1:8765/index.html#/165")
print("art165", "坟照" in art, "images/image3.webp" in art)
q = dump("http://127.0.0.1:8765/index.html#/014")
print("art014", "问题描述" in q, "世界就是这样的" in q)

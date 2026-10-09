import html, json, os, re, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BBC = "https://feeds.bbci.co.uk/news/"
FEEDS = {"top": BBC + "rss.xml", "world": BBC + "world/rss.xml", "africa": BBC + "world/africa/rss.xml",
         "business": BBC + "business/rss.xml", "technology": BBC + "technology/rss.xml",
         "science": BBC + "science_and_environment/rss.xml", "health": BBC + "health/rss.xml",
         "sport": "https://feeds.bbci.co.uk/sport/rss.xml", "entertainment": BBC + "entertainment_and_arts/rss.xml"}
GOOGLE = "https://news.google.com/rss/search?q=%s&hl=en-NG&gl=NG&ceid=NG:en"
MEDIA = "{http://search.yahoo.com/mrss/}"
cache = {}

def parse(xml, default_source):
    items = []
    for it in ET.fromstring(xml).iter("item"):
        title, link = (it.findtext("title") or "").strip(), (it.findtext("link") or "").strip()
        if not title or not link:
            continue
        src = it.find("source")
        source = (src.text if src is not None and src.text else default_source)
        if source and title.endswith(" - " + source):
            title = title[: -len(source) - 3]
        desc = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", it.findtext("description") or ""))).strip()
        if desc[:25] == title[:25]:
            desc = ""
        th = it.find(MEDIA + "thumbnail")
        try:
            ts = parsedate_to_datetime(it.findtext("pubDate")).timestamp()
        except Exception:
            ts = 0
        items.append({"title": title, "link": link, "desc": desc[:220], "source": source,
                      "img": th.get("url") if th is not None else "", "ts": ts})
    return items[:30]

def get(cat, q):
    key = (cat, q)
    hit = cache.get(key)
    if hit and time.time() - hit[0] < 300:
        return hit[1]
    try:
        url = GOOGLE % urllib.parse.quote(q) if cat == "search" else FEEDS[cat]
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 headlines-site"})
        data = json.dumps({"items": parse(urllib.request.urlopen(req, timeout=15).read(), "BBC News" if cat != "search" else "")}).encode()
        cache[key] = (time.time(), data)
        return data
    except Exception:
        return hit[1] if hit else None

class H(BaseHTTPRequestHandler):
    def reply(self, status, body, ctype):
        self.send_response(status); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        if u.path == "/api":
            qs = urllib.parse.parse_qs(u.query)
            cat, q = qs.get("cat", [""])[0], qs.get("q", [""])[0].strip()[:80]
            if not (cat in FEEDS or (cat == "search" and q)):
                return self.reply(400, b'{"error":"bad request"}', "application/json")
            body = get(cat, q if cat == "search" else "")
            return self.reply(200, body, "application/json") if body else self.reply(502, b'{"error":"upstream"}', "application/json")
        if u.path in ("/", "/index.html"):
            return self.reply(200, (Path(__file__).parent / "index.html").read_bytes(), "text/html; charset=utf-8")
        self.reply(404, b"Not found", "text/plain")

    def log_message(self, *a):
        pass

if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", int(os.getenv("PORT", "8000"))), H).serve_forever()

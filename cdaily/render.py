"""Turn a proverb + Claude's content into slide images (HTML rendered with headless Chromium)."""
import base64, html, math, re
from .core import ASSETS, DIALECT_LABEL, letters, translit

FEED, TALL = (1080, 1350), (1080, 1920)          # carousel slide; story and reel frame
HANDLE = "@circassian_daily"
FONTS = {"serif": ("'Noto Serif'", "'Noto Naskh Arabic'"), "sans": ("'Noto Sans'", "'Noto Kufi Arabic'"),
         "display": ("'Noto Serif Display','Noto Serif'", "'Noto Naskh Arabic'")}
FONT_URL = ("https://fonts.googleapis.com/css2?family=Noto+Serif:wght@400;600;700&family=Noto+Sans:wght@400;600;700"
            "&family=Noto+Serif+Display:wght@500;700&family=Noto+Naskh+Arabic:wght@400;600;700"
            "&family=Noto+Kufi+Arabic:wght@400;600&display=swap")

CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:%(w)spx;height:%(h)spx}
body{font-family:%(lat)s,'DejaVu Serif',serif;color:%(ink)s;background:%(bgcss)s;
  position:relative;overflow:hidden}
.ar{font-family:%(ar)s,'Noto Naskh Arabic','DejaVu Sans',serif;direction:rtl;unicode-bidi:isolate;line-height:1.7}
.motif{position:absolute;color:%(accent)s;opacity:%(mop)s;width:%(mw)spx;height:%(mw)spx;right:-140px;bottom:-140px}
.motif svg{width:100%%;height:100%%}
.split .motif{opacity:.5;right:auto;left:50%%;transform:translateX(-50%%);top:%(mt)spx;bottom:auto;width:%(ms)spx;height:%(ms)spx}
.wrap{position:absolute;inset:0;z-index:1;padding:%(pad)s;display:flex;flex-direction:column}
.top{display:flex;justify-content:space-between;align-items:center;gap:24px}
.logo{height:%(logo)spx;width:%(logo)spx;border-radius:50%%;object-fit:cover;box-shadow:0 6px 18px rgba(0,0,0,.22)}
.brand{font-size:30px;letter-spacing:.04em;color:%(muted)s;font-weight:600}
.chip{font-size:24px;color:%(accent)s;border:2px solid %(accent)s;border-radius:999px;padding:8px 22px;white-space:nowrap}
.body{flex:1;display:flex;flex-direction:column;justify-content:center;gap:%(gap)spx}
.centered .body,.framed .body,.split .body{text-align:center;align-items:center}
.split .body{justify-content:flex-end;padding-bottom:20px}
.left .body{border-left:10px solid %(accent)s;padding-left:44px}
.framed .wrap{margin:36px;inset:0;border:3px solid %(accent)s;border-radius:28px;padding:%(padf)s}
.cyr{font-weight:700;line-height:1.25}
.lat{color:%(muted)s;font-style:italic;font-size:34px}
.en{font-size:44px;line-height:1.35}
.rule{width:140px;height:5px;background:%(accent)s;border-radius:3px}
.left .rule{margin:0}
.foot{display:flex;justify-content:space-between;align-items:flex-end;color:%(muted)s;font-size:26px;gap:20px}
.foot .ar{white-space:nowrap}
.kicker{color:%(accent)s;font-size:30px;letter-spacing:.14em;text-transform:uppercase;font-weight:600}
.kind{display:flex;flex-wrap:wrap;align-items:baseline;gap:8px 22px;color:%(accent)s;font-weight:600;max-width:100%%}
.kind span{white-space:nowrap;flex:none}
.centered .kind,.framed .kind,.split .kind{justify-content:center}
.kind .k-en{font-size:%(kind)spx;letter-spacing:.16em;text-transform:uppercase}
.kind .k-dot{opacity:.6;font-size:%(kind)spx}
.kind .ar{font-size:%(kindar)spx;line-height:1.2;letter-spacing:0}
.word{font-size:%(wordsize)spx;font-weight:700;line-height:1.15}
.letters{display:flex;flex-wrap:wrap;gap:12px;justify-content:inherit}
.centered .letters,.framed .letters,.split .letters{justify-content:center}
.letters span{min-width:70px;text-align:center;font-size:40px;padding:10px 14px;border-radius:14px;
  background:%(chipbg)s;border:2px solid %(accent)s}
.gloss{font-size:46px;line-height:1.3}
.note{font-size:30px;color:%(muted)s;line-height:1.45}
.pair{display:flex;flex-direction:column;gap:22px;width:100%%}
.sep{height:2px;background:%(muted)s;opacity:.35;width:100%%;margin:10px 0}
"""


import datetime as _dt
import functools

# Eight looks that rotate day by day (light and dark alternate), so neighbouring posts never look alike.
# Claude still draws the motif for each proverb; the palette, type and layout come from here.
STYLES = [
    dict(name="parchment", light=True, bg="#F4ECD8", bg2="#E6D7B8", ink="#2B2118", accent="#9C2F1F", muted="#6B5B4A",
         font="serif", layout="framed", grad="radial"),
    dict(name="forest", bg="#12402F", bg2="#071F17", ink="#F3EBD3", accent="#D4A84B", muted="#A9C2B4",
         font="display", layout="centered", angle=170),
    dict(name="snow", light=True, bg="#EEF5F8", bg2="#C9DCE6", ink="#13303F", accent="#1F6F8B", muted="#4E6B78",
         font="sans", layout="split", angle=180),
    dict(name="pomegranate", bg="#86202A", bg2="#420B12", ink="#FBEFE3", accent="#F2C14E", muted="#E6BDB4",
         font="serif", layout="left", angle=135),
    dict(name="sage", light=True, bg="#E3E8CF", bg2="#C3CDA2", ink="#26301A", accent="#55692A", muted="#5E6650",
         font="serif", layout="left", angle=200),
    dict(name="charcoal", bg="#222020", bg2="#0E0D0C", ink="#F5F0E6", accent="#C9A227", muted="#A39A8C",
         font="display", layout="framed", grad="radial"),
    dict(name="terracotta", bg="#C8643B", bg2="#8E3B21", ink="#FFF6EC", accent="#FFE1B0", muted="#F8D3BC",
         font="sans", layout="centered", angle=150),
    dict(name="indigo", bg="#232A63", bg2="#0C0E2C", ink="#EDEBFF", accent="#9DBBFF", muted="#B4B3D6",
         font="display", layout="split", angle=165),
]


def style_for(day, design):
    """Today's look: the rotating palette/type/layout plus the motif Claude drew for this proverb."""
    st = STYLES[_dt.date.fromisoformat(day).toordinal() % len(STYLES)]
    svg = re.sub(r'(fill|stroke)\s*=\s*"(?!none|currentColor)[^"]*"', r'\1="currentColor"', design.get("motif_svg") or "")
    return dict(design, **{k: v for k, v in st.items() if k != "name"}, style=st["name"], motif_svg=svg)




@functools.lru_cache(maxsize=1)
def _logo():
    for name in ("logo.png", "logo.jpg", "logo.jpeg", "logo.webp"):
        f = ASSETS / name
        if f.exists():
            mime = "image/" + ("jpeg" if name.endswith(("jpg", "jpeg")) else name.rsplit(".", 1)[1])
            return f'<img class="logo" src="data:{mime};base64,{base64.b64encode(f.read_bytes()).decode()}">'
    return ""


def _fit(text, big, small, at=28, floor=90):
    """Font size that shrinks as the text gets longer."""
    n = len(text)
    return big if n <= at else max(small, int(big - (big - small) * min(1, (n - at) / (floor - at))))


def _page(body, d, size, wordsize=120):
    w, h = size
    tall = h > 1400
    lat, ar = FONTS[d["font"]]
    grad = d.get("grad", "linear")
    bgcss = (f'radial-gradient(circle at 30% 20%, {d["bg"]} 0%, {d["bg2"]} 85%)' if grad == "radial" else
             f'linear-gradient({d.get("angle", 160)}deg, {d["bg"]} 0%, {d["bg2"]} 100%)')
    light = d.get("light", False)
    css = CSS % dict(w=w, h=h, lat=lat, ar=ar, ink=d["ink"], bgcss=bgcss, accent=d["accent"],
                     mop=".22" if light else ".14", chipbg="rgba(0,0,0,.05)" if light else "rgba(255,255,255,.10)",
                     muted=d["muted"], pad="250px 100px 340px" if tall else "80px", padf="214px 70px 304px" if tall else "64px",
                     logo=132 if tall else 116, kind=28, kindar=38 if tall else 36, gap=44 if tall else 34,
                     mw=820, ms=440 if tall else 300, mt=250 if tall else 150, wordsize=wordsize)
    motif = f'<div class="motif">{d["motif_svg"]}</div>' if d["motif_svg"] else ""
    return (f'<!doctype html><html><head><meta charset="utf-8"><link rel="stylesheet" href="{FONT_URL}">'
            f'<style>{css}</style></head><body class="{d["layout"]}">{motif}<div class="wrap">{body}</div></body></html>')


def _top(p):
    lab = DIALECT_LABEL[p["dialect"]]
    logo = _logo() or f'<div class="brand">{HANDLE}</div>'
    return f'<div class="top">{logo}<div class="chip">{html.escape(lab["en"])}</div></div>'


def _foot(p, right=""):
    lab = DIALECT_LABEL[p["dialect"]]
    left = HANDLE if _logo() else html.escape(right)          # the handle is already at the top when there is no logo
    return (f'<div class="foot"><div>{left}</div>'
            f'<div class="ar" style="font-size:26px">{html.escape(lab["ar"])}</div></div>')


# What kind of post this is, printed on the cover and the story. Add a line here for each new kind of post.
KINDS = {"proverb": ("Circassian Proverb", "مثل شركسي")}


def _kind(p):
    en, ar = KINDS.get(p.get("kind", "proverb"), KINDS["proverb"])
    return (f'<div class="kind"><span class="k-en">{html.escape(en)}</span><span class="k-dot">·</span>'
            f'<span class="ar">{html.escape(ar)}</span></div>')


def cover(p, c, size):
    cyr = p["circassian"]
    fs = _fit(cyr, 88, 52) if size == FEED else _fit(cyr, 100, 60)
    body = (_top(p) + '<div class="body">' + _kind(p) +
            f'<div class="cyr" style="font-size:{fs}px">{html.escape(cyr)}</div>'
            f'<div class="lat">{html.escape(p["latin"])}</div><div class="rule"></div>'
            f'<div class="ar" style="font-size:{_fit(p["arabic"], 56, 40, 40, 140)}px">{html.escape(p["arabic"])}</div>'
            f'<div class="en" style="font-size:{_fit(p["english"], 46, 34, 60, 170)}px">{html.escape(p["english"])}</div>'
            '</div>' + _foot(p))
    d = c["design"]
    if d.get("layout") == "split" and (len(cyr) > 30 or len(p["english"]) > 70 or len(p["arabic"]) > 60):
        d = dict(d, layout="centered")          # a long proverb needs the room the picture would take
    return _page(body, d, size)


def word_slide(p, c, group, start, total, size):
    parts = []
    for w in group:
        chips = "".join(f"<span>{html.escape(x)}</span>" for x in letters(w["cyr"], p["dialect"]))
        note = f'<div class="note">{html.escape(w["note_en"])}</div>' if w["note_en"] else ""
        note_ar = f'<div class="note ar">{html.escape(w["note_ar"])}</div>' if w["note_ar"] else ""
        parts.append('<div class="pair">'
                     f'<div class="word">{html.escape(w["cyr"])}</div>'
                     f'<div class="lat">{html.escape(translit(w["cyr"]))}</div>'
                     f'<div class="letters">{chips}</div>'
                     f'<div class="gloss">{html.escape(w["en"])}</div>'
                     f'<div class="gloss ar">{html.escape(w["ar"])}</div>{note}{note_ar}</div>')
    end = start + len(group) - 1
    label = f"Word {start} of {total}" if len(group) == 1 else f"Words {start}–{end} of {total}"
    d = dict(c["design"], layout="left" if c["design"]["layout"] == "split" else c["design"]["layout"])
    longest = max(len(w["cyr"]) for w in group)
    wordsize = (130 if longest <= 9 else 100 if longest <= 14 else 78) - (30 if len(group) > 1 else 0)
    body = (_top(p) + f'<div class="body"><div class="kicker">{label}</div>' + '<div class="sep"></div>'.join(parts)
            + '</div>' + _foot(p))
    return _page(body, d, size, wordsize)


def closing(p, c, size):
    body = (_top(p) + '<div class="body"><div class="kicker">The meaning</div>'
            f'<div class="cyr" style="font-size:{_fit(p["circassian"], 60, 42)}px">{html.escape(p["circassian"])}</div>'
            '<div class="rule"></div>'
            f'<div class="en" style="font-size:38px">{html.escape(c["meaning_en"])}</div>'
            f'<div class="ar" style="font-size:40px">{html.escape(c["meaning_ar"])}</div>'
            f'<div class="kicker" style="margin-top:20px">Follow {HANDLE}</div></div>' + _foot(p))
    return _page(body, c["design"], size)


def slides(p, c, size):
    """All slides in order: cover, word-by-word, meaning. At most 10, Instagram's safe carousel size."""
    words = c["words"]
    per = max(1, math.ceil(len(words) / 8))
    out = [cover(p, c, size)]
    for i in range(0, len(words), per):
        out.append(word_slide(p, c, words[i:i + per], i + 1, len(words), size))
    out.append(closing(p, c, size))
    return out


def screenshot(pages, paths, size):
    """Render each HTML page to a PNG. Needs: pip install playwright && playwright install chromium."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch()
        except Exception:
            browser = pw.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": size[0], "height": size[1]})
        for doc, path in zip(pages, paths):
            page.set_content(doc, wait_until="load")
            try:
                page.wait_for_function("document.fonts.status === 'loaded'", timeout=15000)
            except Exception:
                pass
            page.screenshot(path=str(path), type="jpeg", quality=92)
        browser.close()

"""Ask Claude for the word-by-word breakdown, the caption and a design for one proverb."""
import json, re, urllib.request
from .core import env, split_words

API = "https://api.anthropic.com/v1/messages"

SYSTEM = """You prepare daily Instagram posts for @circassian_daily, a page that teaches Circassian proverbs.
You are careful with the Circassian (Adyghe/Kabardian) language: never change the spelling of the proverb or its words.
Reply with one JSON object and nothing else."""

PROMPT = """Proverb ({dialect} dialect): {cyr}
Latin transliteration: {lat}
English: {en}
Arabic: {ar}
Theme: {theme}

The proverb's words, in order: {words}

Return JSON with exactly these keys:
- "words": one object per word above, same order and same count. Each: {{"cyr": the word exactly as given,
  "en": its meaning in this proverb (2-6 words), "ar": the same in Arabic,
  "note_en": one short sentence on its form (root, prefix/suffix, case or verb form) or "" if unsure,
  "note_ar": the same note in Arabic or ""}}. If you are not sure of a word, give your best gloss and set "unsure": true.
- "meaning_en": 1-2 sentences on what the proverb teaches. "meaning_ar": the same in Arabic.
- "caption": an Instagram caption in English then Arabic (under 600 characters in total), no hashtags.
- "hashtags": 8-12 hashtags without the # sign, mixing English, Arabic and Circassian topics.
- "design": a distinct visual identity for THIS proverb, inspired by its imagery:
  {{"bg": "#hex", "bg2": "#hex" (second background tone for a gradient), "ink": "#hex" (main text),
    "accent": "#hex", "muted": "#hex" (secondary text), "layout": one of "centered", "left", "framed", "split",
    "font": one of "serif", "sans", "display",
    "motif_svg": an original SVG illustration of the proverb's central image (for example a wolf and a forest,
      a sword, a hearth, a mountain, bees) drawn with simple shapes in a flat, elegant style; it may also draw on
      Circassian ornament. Rules: root <svg viewBox="0 0 400 400">, only path/circle/ellipse/rect/line/polygon/polyline/g,
      colours only from this palette or "currentColor", no text, no images, no scripts, no external references,
      under 6000 characters.}}
  Text must stay readable: contrast between "ink" and both backgrounds must be high. Vary palettes from day to day."""


def _call(prompt):
    body = json.dumps({
        "model": env("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
        "max_tokens": 6000,
        "system": SYSTEM,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(API, data=body, headers={
        "content-type": "application/json", "anthropic-version": "2023-06-01",
        "x-api-key": env("ANTHROPIC_API_KEY", required=True)})
    with urllib.request.urlopen(req, timeout=180) as r:
        data = json.load(r)
    return "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")


def _json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ValueError("Claude did not return JSON")
    return json.loads(m.group(0))


HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
DEFAULT_DESIGN = {"bg": "#12372A", "bg2": "#0B2219", "ink": "#FBF6E9", "accent": "#E0B341", "muted": "#B9C4B5",
                  "layout": "centered", "font": "serif", "motif_svg": ""}
SVG_OK = {"svg", "g", "path", "circle", "ellipse", "rect", "line", "polygon", "polyline"}


def clean_svg(svg):
    """Keep only a plain drawing: drop anything that could load or run something."""
    if not isinstance(svg, str) or "<svg" not in svg or len(svg) > 9000:
        return ""
    svg = svg[svg.index("<svg"):svg.rindex("</svg>") + 6] if "</svg>" in svg else ""
    if re.search(r"(?i)<\s*(script|foreignObject|image|use|style|a|iframe|text)\b|on\w+\s*=|href|url\(|javascript:", svg):
        return ""
    tags = set(t.lower() for t in re.findall(r"<\s*([A-Za-z]+)", svg))
    return svg if tags <= SVG_OK else ""


def clean_design(d):
    out = dict(DEFAULT_DESIGN)
    if isinstance(d, dict):
        for k in ("bg", "bg2", "ink", "accent", "muted"):
            if isinstance(d.get(k), str) and HEX.match(d[k]):
                out[k] = d[k]
        if d.get("layout") in ("centered", "left", "framed", "split"):
            out["layout"] = d["layout"]
        if d.get("font") in ("serif", "sans", "display"):
            out["font"] = d["font"]
        out["motif_svg"] = clean_svg(d.get("motif_svg", ""))
    return out


def build_content(p, mock=False):
    """Content for one proverb. With mock=True nothing is sent to the API (for layout tests)."""
    words = split_words(p["circassian"])
    if mock:
        raw = {"words": [{"cyr": w, "en": "(meaning)", "ar": "(المعنى)", "note_en": "", "note_ar": ""} for w in words],
               "meaning_en": p["english"], "meaning_ar": p["arabic"], "caption": p["english"] + "\n\n" + p["arabic"],
               "hashtags": ["circassian", "adyghe", "proverbs"], "design": {
                   "motif_svg": '<svg viewBox="0 0 400 400"><circle cx="200" cy="200" r="150" fill="none" stroke="currentColor" stroke-width="6"/><path d="M80 260 L200 90 L320 260 Z" fill="currentColor"/></svg>'}}
    else:
        raw = _json(_call(PROMPT.format(dialect=p["dialect"].title(), cyr=p["circassian"], lat=p["latin"],
                                        en=p["english"], ar=p["arabic"], theme=p["theme"],
                                        words=json.dumps(words, ensure_ascii=False))))
    got = raw.get("words") or []
    fixed = []
    for i, w in enumerate(words):                      # the spelling always comes from our data, never from the model
        g = got[i] if i < len(got) and isinstance(got[i], dict) else {}
        fixed.append({"cyr": w, "en": str(g.get("en", "")), "ar": str(g.get("ar", "")),
                      "note_en": str(g.get("note_en", "")), "note_ar": str(g.get("note_ar", "")),
                      "unsure": bool(g.get("unsure")) or len(got) != len(words)})
    tags = [re.sub(r"[^\w]", "", str(t)) for t in raw.get("hashtags", [])][:12]
    return {"words": fixed, "meaning_en": str(raw.get("meaning_en", p["english"])),
            "meaning_ar": str(raw.get("meaning_ar", p["arabic"])), "caption": str(raw.get("caption", p["english"])),
            "hashtags": [t for t in tags if t], "design": clean_design(raw.get("design"))}

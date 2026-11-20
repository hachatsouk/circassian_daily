"""Settings, proverb store, Circassian spelling helpers."""
import csv, json, os, random, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA, OUT, ASSETS = ROOT / "data", ROOT / "output", ROOT / "assets"
STATE = DATA / "state.json"
PAL = "Ӏ"  # Cyrillic palochka


def load_env():
    """Read .env (KEY=VALUE lines) into the environment without overriding real env vars."""
    f = ROOT / ".env"
    if f.exists():
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def env(name, default=None, required=False):
    v = os.environ.get(name, default)
    if required and not v:
        raise SystemExit(f"Missing setting {name}. Put it in .env (see .env.example).")
    return v


# ---------- proverbs ----------
def load_proverbs():
    with open(DATA / "proverbs.csv", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["id"] = int(r["id"])
    return rows


def load_state():
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"posted": {}}


def save_state(state):
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")


def pick_proverb(state, proverb_id=None):
    """Next unposted proverb in a fixed shuffled order (so reruns pick the same one)."""
    rows = load_proverbs()
    if proverb_id:
        return next(r for r in rows if r["id"] == int(proverb_id))
    order = rows[:]
    random.Random(1864).shuffle(order)
    done = set(map(int, state["posted"]))
    for r in order:
        if r["id"] not in done:
            return r
    raise SystemExit("Every proverb has been posted. Add more rows to data/proverbs.csv.")


# ---------- spelling ----------
# Letters of the two literary alphabets that are written with more than one character.
MULTI = {
    "kabardian": ["кхъу", "кхъ", "къу", "къ", "кӏу", "кӏ", "ку", "гъу", "гъ", "гу", "хъу", "хъ", "хь", "дж", "дз",
                  "жь", "лъ", "лӏ", "пӏ", "тӏ", "фӏ", "цӏ", "щӏ", "ӏу", "ӏ"],
    "adyghe": ["къу", "къ", "кӏу", "кӏ", "ку", "гъу", "гъ", "гу", "хъу", "хъ", "хь", "дзу", "дж", "дз", "жъу", "жъ",
               "жь", "лъ", "лӏ", "пӏу", "пӏ", "тӏу", "тӏ", "цу", "цӏ", "чъ", "чӏ", "шъу", "шъ", "шӏу", "шӏ", "ӏу", "ӏ"],
}
LATIN_MULTI = [("кхъ", "qh"), ("къ", "q"), ("кӏ", "k'"), ("гъ", "gh"), ("хъ", "kh"), ("хь", "h"), ("дж", "j"),
               ("дз", "dz"), ("жъ", "zhh"), ("жь", "zch"), ("шъ", "shh"), ("шӏ", "sh'"), ("щӏ", "sch'"), ("чъ", "chh"),
               ("чӏ", "ch'"), ("цӏ", "ts'"), ("лъ", "lh"), ("лӏ", "l'"), ("пӏ", "p'"), ("тӏ", "t'"), ("фӏ", "f'")]
LATIN_ONE = {"б": "b", "в": "v", "г": "g", "д": "d", "ж": "zh", "з": "z", "й": "y", "к": "k", "л": "l", "м": "m",
             "н": "n", "п": "p", "р": "r", "с": "s", "т": "t", "ф": "f", "х": "x", "ц": "ts", "ч": "ch", "ш": "sh",
             "щ": "sch", "ӏ": "'"}
LATIN_VOW = {"а": "a", "э": "e", "ы": "ı", "и": "i", "о": "o", "я": "ya", "ю": "yu", "ё": "yo"}
VOWELS = set("аэыиеоуяюё")


def _low(s):
    return s.lower().replace(PAL, "ӏ").replace("ӏ", "ӏ")


def translit(s):
    t, out, i, prev = _low(s), [], 0, "none"
    while i < len(t):
        for k, v in LATIN_MULTI:
            if t.startswith(k, i):
                out.append(v); i += len(k); prev = "c"; break
        else:
            ch, nxt = t[i], t[i + 1:i + 2]
            if ch == "у":
                out.append("w" if (nxt in VOWELS and nxt and nxt != "у") else "u"); prev = "v"
            elif ch == "е":
                out.append("é" if prev == "c" else "ye"); prev = "v"
            elif ch in LATIN_VOW:
                out.append(LATIN_VOW[ch]); prev = "v"
            elif ch in LATIN_ONE:
                out.append(LATIN_ONE[ch]); prev = "c"
            elif ch not in "ъь":
                out.append(ch); prev = "none"
            i += 1
    return "".join(out)


def letters(word, dialect):
    """Split a word into the letters of its alphabet, keeping multi-character letters together."""
    t, out, i = _low(word), [], 0
    multi = MULTI["kabardian" if dialect.startswith("kab") else "adyghe"]
    while i < len(t):
        for k in multi:
            if t.startswith(k, i):
                out.append(word[i:i + len(k)]); i += len(k); break
        else:
            out.append(word[i]); i += 1
    return [x.replace("ӏ", PAL) for x in out]


def split_words(text):
    """Words of a proverb in order, without punctuation."""
    return [w for w in re.findall(r"[А-Яа-яЁёӀӏ]+(?:-[А-Яа-яЁёӀӏ]+)*", text)]


DIALECT_LABEL = {
    "kabardian": {"en": "Kabardian dialect (East Circassian)", "ar": "اللهجة القباردية (الشركسية الشرقية)", "cyr": "Къэбэрдеибзэ"},
    "adyghe": {"en": "Adyghe dialect (West Circassian)", "ar": "اللهجة الأديغية (الشركسية الغربية)", "cyr": "КӀахыбзэ"},
}

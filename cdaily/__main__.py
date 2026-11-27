"""Circassian Daily: one proverb a day to Instagram (carousel, reel and story) through Buffer.

  python -m cdaily channels            list Buffer channels, to find BUFFER_CHANNEL_ID
  python -m cdaily prepare             pick today's proverb, ask Claude, render images and the reel
  python -m cdaily publish             send today's prepared post to Buffer
  python -m cdaily run                 prepare, then publish
  python -m cdaily setup               ask for the keys, find the Instagram channel, make a test post locally
  python -m cdaily github              create the GitHub repository, store the secrets, switch on the daily run
  python -m cdaily check --days 7      print skip=true if the queue already reaches 7 days ahead (used by the daily run)
Add --days 7 to prepare/publish/run to queue a week of posts in Buffer, each at POST_TIME on its own day.
Options: --date YYYY-MM-DD, --id N (a specific proverb), --mock (no Claude call), --dry-run (no Buffer call)
"""
import argparse, datetime as dt, getpass, json, os, shutil, subprocess, sys
from zoneinfo import ZoneInfo
from . import ai, publish as pub, render
from .core import DIALECT_LABEL, OUT, ROOT, env, load_env, load_state, pick_proverb, save_state


def today():
    return dt.datetime.now(ZoneInfo(env("TIMEZONE", "Asia/Amman"))).date().isoformat()


def posted_today():
    return today() in load_state()["posted"].values()


def days(args):
    """The dates to work on: --date (or today), and the following days when --days N is given."""
    start = dt.date.fromisoformat(args.date or today())
    return [(start + dt.timedelta(d)).isoformat() for d in range(max(1, args.days))]


def planned_ids():
    """Proverbs already prepared for some day (posted or waiting in Buffer)."""
    ids = set()
    for f in OUT.glob("*/post.json"):
        try:
            ids.add(int(json.loads(f.read_text(encoding="utf-8"))["proverb"]["id"]))
        except Exception:
            pass
    return ids


def prepare(args):
    for day in days(args):
        if (OUT / day / "post.json").exists() and not args.force:
            print(f"{day}: already prepared, keeping it.")
            continue
        prepare_day(args, day)


def prepare_day(args, day):
    folder = OUT / day
    folder.mkdir(parents=True, exist_ok=True)
    p = pick_proverb(load_state(), args.id, exclude=planned_ids())
    c = ai.build_content(p, mock=args.mock)
    c["design"] = render.style_for(day, c["design"])                   # a different look every day
    feed = render.slides(p, c, render.FEED)
    tall = render.slides(p, c, render.TALL)
    feed_files = [folder / f"slide_{i:02d}.jpg" for i in range(1, len(feed) + 1)]
    tall_files = [folder / f"frame_{i:02d}.jpg" for i in range(1, len(tall) + 1)]
    render.screenshot(feed, feed_files, render.FEED)
    render.screenshot(tall, tall_files, render.TALL)
    story = folder / "story.jpg"
    story.write_bytes(tall_files[0].read_bytes())                      # the story is the proverb page only
    reel = pub.make_reel(tall_files, folder / "reel.mp4", float(env("REEL_SECONDS_PER_SLIDE", "3.5")))
    for f in tall_files:
        f.unlink()
    lab = DIALECT_LABEL[p["dialect"]]
    caption = (f'{p["circassian"]}\n\n{p["arabic"]}\n{p["english"]}\n\n{c["caption"]}\n\n{lab["en"]} · {lab["ar"]}\n\n'
               + " ".join("#" + t for t in c["hashtags"]))
    post = {"date": day, "proverb": p, "content": c, "caption": caption,
            "slides": [f.name for f in feed_files], "story": story.name, "reel": reel.name}
    (folder / "post.json").write_text(json.dumps(post, ensure_ascii=False, indent=1), encoding="utf-8")
    unsure = [w["cyr"] for w in c["words"] if w["unsure"]]
    print(f"Prepared {day}: proverb #{p['id']} ({p['dialect']}), {len(feed_files)} slides, reel and story in {folder}")
    if unsure:
        print("Claude was unsure about these words, check them before posting:", ", ".join(unsure))
    return post


def due_at(day):
    """POST_TIME on that day if it is still ahead of us, otherwise None (post now)."""
    t = env("POST_TIME", "")
    if not t:
        return None
    tz = ZoneInfo(env("TIMEZONE", "Asia/Amman"))
    now = dt.datetime.now(tz)
    h, m = map(int, t.split(":"))
    when = dt.datetime.combine(dt.date.fromisoformat(day), dt.time(h, m), tz)
    return when.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if when > now + dt.timedelta(minutes=2) else None


def publish(args):
    for day in days(args):
        publish_day(args, day)


def publish_day(args, day):
    folder = OUT / day
    f = folder / "post.json"
    if not f.exists():
        raise SystemExit(f"Nothing prepared for {day}. Run: python -m cdaily prepare")
    post = json.loads(f.read_text(encoding="utf-8"))
    state = load_state()
    pid = str(post["proverb"]["id"])
    if pid in state["posted"] and not args.force:
        print(f"{day}: proverb #{pid} is already with Buffer ({state['posted'][pid]}), skipping.")
        return
    base = env("MEDIA_BASE_URL", required=True).rstrip("/") + "/" + day + "/"
    slides = [base + s for s in post["slides"]]
    story, reel = base + post["story"], base + post["reel"]
    if args.dry_run:
        print("Dry run. Would send to Buffer:\n carousel:", *slides, "\n reel:", reel, "\n story:", story, "\n\n" + post["caption"])
        return
    pub.wait_public(slides + [story, reel])
    when = due_at(day)
    if not when and day != today():
        raise SystemExit(f"{day}: its posting time has passed but it is not today; refusing to post it now.")
    alt = post["proverb"]["english"]
    bfile = folder / "buffer.json"
    ids = json.loads(bfile.read_text(encoding="utf-8")) if bfile.exists() else {}      # pieces already with Buffer
    pieces = [
        ("carousel", "post", post["caption"], [{"image": {"url": u, "metadata": {"altText": alt}}} for u in slides]),
        ("reel", "reel", post["caption"], [{"video": {"url": reel}}]),
        ("story", "story", "", [{"image": {"url": story, "metadata": {"altText": alt}}}]),
    ]
    for name, kind, text, assets in pieces:
        if name in ids:
            continue                                   # never send the same piece twice
        ids[name] = pub.create_post(kind, text, assets, when)
        bfile.write_text(json.dumps(ids, indent=1), encoding="utf-8")
    state["posted"][pid] = day
    save_state(state)
    print(f"{day}: sent to Buffer ({'scheduled ' + when if when else 'share now'}):", ids)


def cancel_pending(args):
    """Days listed in data/cancel.txt (one YYYY-MM-DD per line) are taken back out of Buffer's queue,
    so the normal steps afterwards remake them with the current code. Only future days, never one already posted."""
    f = ROOT / "data" / "cancel.txt"
    days_ = [l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip()] if f.exists() else []
    if not days_:
        print("Nothing to cancel.")
        return
    state = load_state()
    for day in days_:
        if day <= today():
            raise SystemExit(f"{day} is today or past; refusing to cancel it (it may already be on Instagram).")
        folder = OUT / day
        bfile = folder / "buffer.json"
        ids = json.loads(bfile.read_text(encoding="utf-8")) if bfile.exists() else {}
        for name, pid in list(ids.items()):
            if pub.delete_post(pid):
                print(f"{day}: removed the queued {name} from Buffer")
            del ids[name]
            bfile.write_text(json.dumps(ids, indent=1), encoding="utf-8")     # progress saved after each piece
        for k, v in list(state["posted"].items()):
            if v == day:
                del state["posted"][k]
        save_state(state)
        if folder.exists():
            (OUT / "cancelled").mkdir(exist_ok=True)
            folder.replace(OUT / "cancelled" / day)
    f.write_text("", encoding="utf-8")
    print("Cancelled:", ", ".join(days_))


def rerender_pending(args):
    """Days listed in data/rerender.txt are drawn again with the current look (for example a new logo): same proverb,
    same words, same design. The old pictures are replaced by new files, and the day is sent to Buffer again by the
    normal publish step. Delete the old Buffer posts first. Only future days."""
    f = ROOT / "data" / "rerender.txt"
    days_ = [l.strip() for l in f.read_text(encoding="utf-8").splitlines() if l.strip()] if f.exists() else []
    if not days_:
        print("Nothing to redraw.")
        return
    state = load_state()
    tag = dt.datetime.now(dt.timezone.utc).strftime("%H%M%S")                # new file names, so no stale cached copy is used
    for day in days_:
        if day <= today():
            raise SystemExit(f"{day} is today or past; refusing to redraw it (it may already be on Instagram).")
        folder = OUT / day
        post = json.loads((folder / "post.json").read_text(encoding="utf-8"))
        p, c = post["proverb"], post["content"]
        feed, tall = render.slides(p, c, render.FEED), render.slides(p, c, render.TALL)
        feed_files = [folder / f"slide_{i:02d}_{tag}.jpg" for i in range(1, len(feed) + 1)]
        tall_files = [folder / f"frame_{i:02d}.jpg" for i in range(1, len(tall) + 1)]
        render.screenshot(feed, feed_files, render.FEED)
        render.screenshot(tall, tall_files, render.TALL)
        story = folder / f"story_{tag}.jpg"
        story.write_bytes(tall_files[0].read_bytes())
        reel = pub.make_reel(tall_files, folder / f"reel_{tag}.mp4", float(env("REEL_SECONDS_PER_SLIDE", "3.5")))
        for t in tall_files:
            t.unlink()
        for old in post["slides"] + [post["story"], post["reel"], "buffer.json"]:
            (folder / old).unlink(missing_ok=True)
        post["slides"], post["story"], post["reel"] = [x.name for x in feed_files], story.name, reel.name
        (folder / "post.json").write_text(json.dumps(post, ensure_ascii=False, indent=1), encoding="utf-8")
        for k, v in list(state["posted"].items()):
            if v == day:
                del state["posted"][k]
        save_state(state)
        print(f"Redrew {day}: proverb #{p['id']}, same design, new pictures.")
    f.write_text("", encoding="utf-8")


def set_env(values):
    """Write KEY=VALUE pairs into .env, keeping the other lines."""
    f = ROOT / ".env"
    src = f if f.exists() else ROOT / ".env.example"
    lines, seen = [], set()
    for line in src.read_text(encoding="utf-8").splitlines():
        k = line.split("=", 1)[0].strip()
        if k in values:
            line = f"{k}={values[k]}"; seen.add(k)
        lines.append(line)
    lines += [f"{k}={v}" for k, v in values.items() if k not in seen]
    f.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ.update(values)


def setup(args):
    print("Circassian Daily setup. Keys are saved only in the .env file in this folder.\n")
    vals = {}
    if not env("ANTHROPIC_API_KEY"):
        vals["ANTHROPIC_API_KEY"] = getpass.getpass("Paste the Anthropic API key (hidden) and press Enter: ").strip()
    if not env("BUFFER_API_KEY"):
        vals["BUFFER_API_KEY"] = getpass.getpass("Paste the Buffer API key (hidden) and press Enter: ").strip()
    if vals:
        set_env(vals)
    if not env("BUFFER_CHANNEL_ID"):
        chans = pub.list_channels()
        insta = [c for c in chans if "instagram" in str(c["service"]).lower()]
        if len(insta) == 1:
            pick = insta[0]
        else:
            for i, c in enumerate(chans, 1):
                print(f'  {i}. {c["service"]:<12} {c["name"]}')
            pick = chans[int(input("Which channel is @circassian_daily? Number: ")) - 1]
        set_env({"BUFFER_CHANNEL_ID": pick["id"]})
        print("Instagram channel:", pick["name"])
    if not shutil.which("ffmpeg"):
        raise SystemExit("ffmpeg was not found. Close this window, open a new one and run setup.bat again.")
    if not any((ROOT / "assets" / n).exists() for n in ("logo.png", "logo.jpg", "logo.jpeg", "logo.webp")):
        print("No logo yet: save the page logo as assets\\logo.png. The pages show the handle until then.")
    post = prepare(args)
    folder = OUT / post["date"]
    print(f"\nTest post ready in {folder}. Nothing has been sent to Instagram.")
    if hasattr(os, "startfile"):
        os.startfile(folder)
    print("Next: run  python -m cdaily github  to switch on the daily run.")


def github(args):
    for tool in ("git", "gh"):
        if not shutil.which(tool):
            raise SystemExit(f"{tool} was not found. Install it (winget install {'GitHub.cli' if tool == 'gh' else 'Git.Git'}), run 'gh auth login', then try again.")
    def run(*cmd, check=True, **kw):
        return subprocess.run(cmd, cwd=ROOT, check=check, **kw)
    wf = ROOT / "daily-workflow.yml"
    if wf.exists():
        (ROOT / ".github" / "workflows").mkdir(parents=True, exist_ok=True)
        wf.replace(ROOT / ".github" / "workflows" / "daily.yml")
    if not (ROOT / ".git").exists():
        run("git", "init", "-b", "main")
    if not run("git", "config", "user.email", check=False, capture_output=True, text=True).stdout.strip():
        who = json.loads(run("gh", "api", "user", capture_output=True, text=True).stdout)   # no git identity yet: use the GitHub one
        run("git", "config", "user.name", who.get("name") or who["login"])
        run("git", "config", "user.email", f'{who["id"]}+{who["login"]}@users.noreply.github.com')
    run("git", "add", "-A")
    run("git", "commit", "-m", "Circassian Daily", check=False)
    if run("git", "remote", "get-url", "origin", check=False, capture_output=True).returncode != 0:
        run("gh", "repo", "create", "circassian_daily", "--public", "--source", ".", "--remote", "origin", "--push")
    else:
        run("git", "push", "-u", "origin", "main")
    for name in ("ANTHROPIC_API_KEY", "BUFFER_API_KEY", "BUFFER_CHANNEL_ID"):
        run("gh", "secret", "set", name, "--body", env(name, required=True))
    print("Done. The repository is public (Buffer needs public media links) and the keys are stored as secrets.")
    url = run("gh", "repo", "view", "--json", "url", "-q", ".url", check=False, capture_output=True, text=True).stdout.strip()
    print("The daily run is on: 08:00 Amman time. Repository:", url)
    print("To post right now: open", url + "/actions/workflows/daily.yml", "and press 'Run workflow'.")


def main():
    load_env()
    ap = argparse.ArgumentParser(prog="cdaily", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["channels", "prepare", "publish", "run", "setup", "github", "check", "cancel", "rerender"])
    ap.add_argument("--date"); ap.add_argument("--id", type=int)
    ap.add_argument("--mock", action="store_true"); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--days", type=int, default=1, help="also prepare/publish the following days (queue ahead in Buffer)")
    args = ap.parse_args()
    if args.command == "channels":
        for ch in pub.list_channels():
            print(f'{ch["id"]}  {ch["service"]:<12} {ch["name"]}')
    elif args.command == "cancel":
        cancel_pending(args)
    elif args.command == "rerender":
        rerender_pending(args)
    elif args.command == "check":
        done = set(load_state()["posted"].values())
        start = dt.date.fromisoformat(today())
        need = [(start + dt.timedelta(d)).isoformat() for d in range(args.days)]
        print("skip=true" if all(d in done for d in need) else "skip=false")
    elif args.command == "setup":
        setup(args)
    elif args.command == "github":
        github(args)
    elif args.command == "prepare":
        prepare(args)
    elif args.command == "publish":
        publish(args)
    else:
        prepare(args); publish(args)


if __name__ == "__main__":
    sys.exit(main())

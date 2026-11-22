"""Reel video (ffmpeg), public media URLs, and posting through Buffer's GraphQL API."""
import json, subprocess, time, urllib.error, urllib.request
from .core import env

BUFFER = "https://api.buffer.com"


def make_reel(frames, out, seconds=3.5):
    """Silent-track MP4 slideshow, 1080x1920, H.264 + AAC, which Instagram accepts as a Reel."""
    lst = out.with_suffix(".txt")
    lines = []
    for f in frames:
        lines += [f"file '{f.resolve().as_posix()}'", f"duration {seconds}"]
    lines.append(f"file '{frames[-1].resolve().as_posix()}'")          # concat needs the last file repeated
    lst.write_text("\n".join(lines), encoding="utf-8")
    total = seconds * len(frames)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=44100",
                    "-vf", "scale=1080:1920,format=yuv420p,fps=30", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                    "-c:a", "aac", "-b:a", "128k", "-t", f"{total:.2f}", "-movflags", "+faststart", str(out)], check=True)
    lst.unlink()
    return out


def wait_public(urls, tries=30, pause=10):
    """Buffer fetches media by URL, so wait until every file is reachable from the internet."""
    for url in urls:
        for _ in range(tries):
            try:
                req = urllib.request.Request(url, method="HEAD")
                if urllib.request.urlopen(req, timeout=20).status == 200:
                    break
            except (urllib.error.URLError, TimeoutError):
                pass
            time.sleep(pause)
        else:
            raise SystemExit(f"Media is not publicly reachable: {url}\nCheck MEDIA_BASE_URL and that the files were pushed.")


def gql(query, variables=None):
    body = json.dumps({"query": query, "variables": variables or {}}).encode()
    req = urllib.request.Request(BUFFER, data=body, headers={
        "Content-Type": "application/json", "Authorization": "Bearer " + env("BUFFER_API_KEY", required=True)})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Buffer API error {e.code}: {e.read().decode()[:500]}")
    if data.get("errors"):
        raise SystemExit("Buffer API error: " + json.dumps(data["errors"])[:800])
    return data["data"]


def list_channels():
    orgs = gql("query { account { organizations { id } } }")["account"]["organizations"]
    out = []
    for o in orgs:
        q = "query($org: OrganizationId!) { channels(input: {organizationId: $org}) { id name service } }"
        out += gql(q, {"org": o["id"]})["channels"]
    return out


CREATE = """mutation($input: CreatePostInput!) { createPost(input: $input) {
  ... on PostActionSuccess { post { id dueAt } }
  ... on MutationError { message } } }"""


def create_post(kind, text, assets, due_at=None):
    """kind is post, reel or story. A carousel is a 'post' with several images.
    If Buffer refuses, this stops with an error. It never falls back to posting straight away."""
    return _create(kind, text, assets, due_at)


def _create(kind, text, assets, due_at):
    inp = {"channelId": env("BUFFER_CHANNEL_ID", required=True), "text": text, "assets": assets,
           "schedulingType": "automatic", "needsApproval": False,
           "mode": "customScheduled" if due_at else "shareNow",
           "metadata": {"instagram": {"type": kind, "shouldShareToFeed": kind != "reel"}}}   # reel: Reels tab only, not the grid
    if due_at:
        inp["dueAt"] = due_at
    res = gql(CREATE, {"input": inp})["createPost"]
    if "post" not in res:
        raise SystemExit(f"Buffer refused the {kind}: {res.get('message', res)}")
    return res["post"]["id"]

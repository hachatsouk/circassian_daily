# Circassian Daily

Posts one Circassian proverb a day to the Instagram page **@circassian_daily** through Buffer:

- **Carousel**: page 1 is the proverb in Circassian, Arabic and English; the next pages go through it word by word
  (the word, its letters one by one, Latin transliteration, Arabic and English meaning); the last page gives the meaning.
- **Reel**: the same pages as a vertical video.
- **Story**: the proverb page only.

Every page carries a small label saying whether the proverb is in the Kabardian or the Adyghe dialect.

## How it works

1. `data/proverbs.csv` holds the 1,073 proverbs (Circassian, Latin, English, Arabic, dialect, theme, source).
2. Each day the next unposted proverb is picked. `data/state.json` remembers what has been posted.
3. Claude (Anthropic API) returns, for that proverb: the word-by-word glosses, a caption and hashtags, and a
   **design of its own**: palette, layout, font style and an SVG illustration of the proverb's image.
4. The pages are rendered to images with headless Chromium, and the reel is assembled with ffmpeg.
5. The files are made public (pushed to the repository), then three posts are created in Buffer: post, reel, story.

The spelling of the proverb and of each word always comes from the CSV, never from Claude.
The letter-by-letter split and the Latin transliteration are done by code, not by Claude.

## Setup

1. Put the page logo at `assets/logo.png`. Without it the pages show the handle instead.
2. Copy `.env.example` to `.env` and fill in `ANTHROPIC_API_KEY` and `BUFFER_API_KEY`.
3. Install: `pip install -r requirements.txt`, then `python -m playwright install chromium`. Install ffmpeg
   (`winget install ffmpeg` on Windows).
4. Run `python -m cdaily channels` and copy the id of the Instagram channel into `BUFFER_CHANNEL_ID`.

## Try it without posting

```
python -m cdaily prepare --mock          # no Claude call: checks rendering only
python -m cdaily prepare                 # real content and design for today
python -m cdaily publish --dry-run       # shows what would be sent to Buffer
```

Look at `output/<date>/` before the first real post. `post.json` holds the glosses Claude wrote.

## Run it every day

**GitHub Actions (recommended).** Push this folder to a **public** GitHub repository and add the repository secrets
`ANTHROPIC_API_KEY`, `BUFFER_API_KEY` and `BUFFER_CHANNEL_ID`. The workflow in `.github/workflows/daily.yml` runs at
08:00 Amman time: it prepares the post, pushes the media, sends it to Buffer and saves the state.
The repository has to be public because Buffer downloads the media from its raw file addresses.

**From this PC.** Schedule `run_daily.bat` in Windows Task Scheduler. Set `MEDIA_BASE_URL` in `.env` to the public
address of the `output` folder.

Any other public host works too: upload `output/<date>/` there and point `MEDIA_BASE_URL` at it.

## Things to know

- **Word glosses need a reader's eye.** Claude's knowledge of Circassian grammar is limited. It flags words it is
  unsure of (`"unsure": true` in `post.json`, also printed by `prepare`), but it can be wrong without flagging.
  To review before posting, run `prepare` the evening before, edit `post.json` if needed, run `prepare` again only if
  you want a new design, and let `publish` run in the morning.
- **Translations.** Many English and Arabic lines in the CSV are unreviewed (see the sheet's "Text check" column).
- **Carousel size.** At most 10 pages. Long proverbs put two or more words on a page.
- **Reel sound.** The reel has a silent audio track. Add music in Buffer or Instagram if you want it.
- **Instagram account.** Buffer can publish reels and stories automatically only for a Business or Creator account
  connected for direct publishing.
- **Posting time.** `POST_TIME=HH:MM` schedules the three posts for that time the same day; empty posts at once.
- **A specific proverb.** `python -m cdaily prepare --id 21`.

## Files

```
cdaily/core.py      settings, proverb picking, spelling and transliteration
cdaily/ai.py        the Claude request and checks on what comes back
cdaily/render.py    page layouts and rendering
cdaily/publish.py   reel, public-media check, Buffer API
cdaily/__main__.py  the commands
```

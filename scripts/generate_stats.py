#!/usr/bin/env python3
"""Generate the profile README's stat graphics straight from GitHub's own
GraphQL API. Standard library only — no third-party badge service, so
nothing here can rate-limit, go stale, or disappear.

Produces, all sharing one visual language:
  stats.svg   total contributions in the last year + a weekly sparkline
  streak.svg  current streak and longest streak
  langs.svg   top languages across your public, non-fork repos
  year.svg    the last year as a contribution heatmap

Every graphic is transparent, respects the viewer's light/dark mode via
`prefers-color-scheme`, and animates once on load with SMIL (not <script> —
GitHub's markdown renderer won't execute JS inside an embedded image anyway,
so SMIL is the only portable way to get a reveal animation).

Env vars:
  GITHUB_TOKEN  required — the default Actions token is enough for public data
  GH_LOGIN      GitHub username to summarise
  OUT_DIR       where to write the .svg files (default: repo root)
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

API_URL = "https://api.github.com/graphql"
WIDTH = 600
LEFT_PAD = 20

QUERY = """
query($login: String!, $since: DateTime!, $until: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $since, to: $until) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date weekday contributionCount } }
      }
    }
    repositories(first: 100, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      nodes {
        languages(first: 10, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name } }
        }
      }
    }
  }
}
"""

# Shared palette: greyscale "ink" for light mode, its dark-mode counterpart,
# plus one accent used sparingly for the current/hero numbers.
COLORS_LIGHT = dict(ink="#24292f", mid="#57606a", dim="#8c959f",
                     line="#d0d7de", accent="#0969da")
COLORS_DARK = dict(ink="#e6edf3", mid="#c9d1d9", dim="#8b949e",
                    line="#30363d", accent="#58a6ff")
FONT_STACK = ("ui-monospace,SFMono-Regular,Menlo,Consolas,"
              "'Liberation Mono',monospace")


# --------------------------------------------------------------------- data

def fetch_contributions(login, token):
    today = datetime.now(timezone.utc).date()
    since = today - timedelta(days=364)
    body = json.dumps({
        "query": QUERY,
        "variables": {
            "login": login,
            "since": f"{since.isoformat()}T00:00:00Z",
            "until": f"{today.isoformat()}T23:59:59Z",
        },
    }).encode()
    req = urllib.request.Request(
        API_URL, data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": f"{login}-profile-stats-script",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        raise SystemExit(f"GitHub GraphQL error: {payload['errors']}")
    user = (payload.get("data") or {}).get("user")
    if not user:
        raise SystemExit(f"GitHub user not found: {login}")
    return user


def compute_streaks(days):
    """Longest run, and the current run ending today (or yesterday if
    today has no contribution yet, since today isn't over)."""
    longest = dict(length=0, start=None, end=None)
    run_len, run_start = 0, None
    for d in days:
        if d["contributionCount"] > 0:
            run_len += 1
            run_start = run_start or d["date"]
            if run_len > longest["length"]:
                longest = dict(length=run_len, start=run_start, end=d["date"])
        else:
            run_len, run_start = 0, None

    current = dict(length=0, start=None, end=None)
    tail = days[:-1] if days and days[-1]["contributionCount"] == 0 else days
    for d in reversed(tail):
        if d["contributionCount"] == 0:
            break
        current["length"] += 1
        current["start"] = d["date"]
        current["end"] = current["end"] or d["date"]
    return current, longest


def top_languages(repo_nodes, limit=6):
    totals = {}
    for repo in repo_nodes:
        for edge in (repo.get("languages") or {}).get("edges") or []:
            name = edge["node"]["name"]
            totals[name] = totals.get(name, 0) + edge["size"]
    ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    return ranked[:limit]


def summarize(user):
    cal = user["contributionsCollection"]["contributionCalendar"]
    weeks = [w["contributionDays"] for w in cal["weeks"]]
    all_days = [d for week in weeks for d in week]
    weekly_totals = [sum(d["contributionCount"] for d in w) for w in weeks]
    current, longest = compute_streaks(all_days)
    return dict(
        total=cal["totalContributions"],
        weeks=weeks,
        weekly_totals=weekly_totals,
        active_days=sum(1 for d in all_days if d["contributionCount"] > 0),
        total_days=len(all_days),
        current_streak=current,
        longest_streak=longest,
        languages=top_languages(user["repositories"]["nodes"]),
    )


# ------------------------------------------------------------------- draw

def svg_open(width, height):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}">')


def style_block():
    def rules(c):
        return (f".ink{{fill:{c['ink']}}}.mid{{fill:{c['mid']}}}"
                f".dim{{fill:{c['dim']}}}.line{{stroke:{c['line']}}}"
                f".accent{{fill:{c['accent']}}}")
    return (f"<style>text{{font-family:{FONT_STACK}}}"
            f"{rules(COLORS_LIGHT)}"
            f"@media(prefers-color-scheme:dark){{{rules(COLORS_DARK)}}}"
            f"</style>")


def fade_in(delay=0.0, dur=0.5):
    return (f'<animate attributeName="opacity" from="0" to="1" '
            f'begin="{delay:.2f}s" dur="{dur:.2f}s" fill="freeze"/>')


def text(x, y, s, size=12, cls="ink", anchor="start", weight="normal"):
    s = s.replace("&", "&amp;").replace("<", "&lt;")
    return (f'<text x="{x}" y="{y}" font-size="{size}" class="{cls}" '
            f'text-anchor="{anchor}" font-weight="{weight}">{s}</text>')


def pretty_date(iso):
    d = datetime.fromisoformat(iso)
    return d.strftime("%b %-d") if os.name != "nt" else d.strftime("%b %d").replace(" 0", " ")


def draw_stats(s):
    height = 150
    p = [svg_open(WIDTH, height), style_block()]
    p.append(f'<g opacity="0">{fade_in(0.05)}'
              + text(LEFT_PAD, 26, "CONTRIBUTIONS, LAST 12 MONTHS", 10, "dim")
              + '</g>')
    p.append(f'<g opacity="0">{fade_in(0.15)}'
              + text(LEFT_PAD, 62, f"{s['total']:,}", 34, "ink", weight="600")
              + text(LEFT_PAD + len(f"{s['total']:,}") * 21 + 10, 62,
                     f"across {s['active_days']} active days", 12, "mid")
              + '</g>')

    # weekly sparkline as bars
    bars = s["weekly_totals"]
    chart_w = WIDTH - LEFT_PAD * 2
    bar_gap = 2
    bar_w = max(1.0, chart_w / len(bars) - bar_gap)
    top_val = max(bars) or 1
    base_y = height - 16
    max_bar_h = 46
    p.append(f'<g opacity="0">{fade_in(0.30)}')
    for i, v in enumerate(bars):
        h = max(1.5, (v / top_val) * max_bar_h)
        x = LEFT_PAD + i * (bar_w + bar_gap)
        y = base_y - h
        cls = "accent" if i == len(bars) - 1 else "mid"
        opacity = 1.0 if v > 0 else 0.15
        p.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" '
                  f'height="{h:.1f}" rx="1" class="{cls}" opacity="{opacity}"/>')
    p.append('</g>')
    p.append(f'<g opacity="0">{fade_in(0.55)}'
              + text(LEFT_PAD, height - 2, "52 weeks ago", 9, "dim")
              + text(WIDTH - LEFT_PAD, height - 2, "this week", 9, "dim", "end")
              + '</g>')
    p.append("</svg>")
    return "".join(p)


def draw_streak(s):
    height = 100
    p = [svg_open(WIDTH, height), style_block()]
    mid_x = WIDTH / 2
    p.append(f'<line x1="{mid_x:.0f}" y1="18" x2="{mid_x:.0f}" y2="86" '
              f'class="line" stroke-width="1" opacity="0">{fade_in(0.1)}</line>')
    blocks = [
        (s["current_streak"], "current streak", LEFT_PAD),
        (s["longest_streak"], "longest streak", mid_x + LEFT_PAD),
    ]
    for i, (streak, label, x) in enumerate(blocks):
        span = (f"{pretty_date(streak['start'])} - {pretty_date(streak['end'])}"
                if streak["length"] else "no active streak yet")
        p.append(f'<g opacity="0">{fade_in(0.15 + i * 0.15)}'
                  + text(x, 46, f"{streak['length']}", 32, "ink", weight="600")
                  + text(x, 66, label, 11, "mid")
                  + text(x, 82, span, 10, "dim")
                  + '</g>')
    p.append("</svg>")
    return "".join(p)


def draw_langs(s):
    langs = s["languages"] or [("no public repos yet", 0)]
    row_h = 22
    height = 30 + len(langs) * row_h
    p = [svg_open(WIDTH, height), style_block()]
    p.append(f'<g opacity="0">{fade_in(0.05)}'
              + text(LEFT_PAD, 20, "TOP LANGUAGES, PUBLIC REPOS", 10, "dim")
              + '</g>')
    total = sum(v for _, v in langs) or 1
    top_val = max(v for _, v in langs) or 1
    name_col = 110
    bar_max = WIDTH - LEFT_PAD * 2 - name_col - 50
    for i, (name, size) in enumerate(langs):
        y = 34 + i * row_h
        pct = size / total * 100 if size else 0
        bar_w = (size / top_val) * bar_max if size else 0
        p.append(f'<g opacity="0">{fade_in(0.15 + i * 0.08)}'
                  + text(LEFT_PAD, y + 10, name, 12, "ink")
                  + f'<rect x="{LEFT_PAD + name_col}" y="{y + 2}" '
                    f'width="{bar_w:.1f}" height="9" rx="2" class="mid"/>'
                  + text(WIDTH - LEFT_PAD, y + 10, f"{pct:.0f}%", 11, "dim", "end")
                  + '</g>')
    p.append("</svg>")
    return "".join(p)


def draw_year(s):
    weeks = s["weeks"]
    cell = 9
    gap = 2
    step = cell + gap
    pad_top = 34
    height = pad_top + 7 * step + 14
    p = [svg_open(WIDTH, height), style_block()]
    p.append(f'<g opacity="0">{fade_in(0.05)}'
              + text(LEFT_PAD, 18, "THE LAST YEAR", 10, "dim")
              + text(WIDTH - LEFT_PAD, 18,
                     f"{s['active_days']}/{s['total_days']} days active",
                     10, "dim", "end")
              + '</g>')

    def level(v):
        if v <= 0:
            return 0.10
        if v <= 2:
            return 0.35
        if v <= 5:
            return 0.6
        if v <= 9:
            return 0.85
        return 1.0

    for wi, week in enumerate(weeks):
        x = LEFT_PAD + wi * step
        for day in week:
            row = day.get("weekday", 0)
            y = pad_top + row * step
            delay = 0.15 + wi * 0.006
            p.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
                      f'rx="2" class="accent" opacity="0">'
                      f'<animate attributeName="opacity" from="0" '
                      f'to="{level(day["contributionCount"])}" '
                      f'begin="{delay:.2f}s" dur="0.4s" fill="freeze"/></rect>')
    p.append("</svg>")
    return "".join(p)


# ------------------------------------------------------------------- main

def write_if_changed(path, content):
    old = ""
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            old = f.read()
    if old == content:
        return False
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return True


def main():
    token = os.environ.get("GITHUB_TOKEN")
    login = os.environ.get("GH_LOGIN")
    out_dir = os.environ.get("OUT_DIR", ".")
    if not token:
        sys.exit("GITHUB_TOKEN is not set")
    if not login:
        sys.exit("GH_LOGIN is not set")

    summary = summarize(fetch_contributions(login, token))
    files = {
        "stats.svg": draw_stats(summary),
        "streak.svg": draw_streak(summary),
        "langs.svg": draw_langs(summary),
        "year.svg": draw_year(summary),
    }
    changed = [name for name, svg in files.items()
               if write_if_changed(os.path.join(out_dir, name), svg)]

    print(f"{summary['total']} contributions, {summary['active_days']} active days, "
          f"current streak {summary['current_streak']['length']}, "
          f"longest {summary['longest_streak']['length']}")
    print("updated: " + (", ".join(changed) if changed else "nothing changed"))


if __name__ == "__main__":
    main()

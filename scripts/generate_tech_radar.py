import os
import math
import json
import urllib.request
import urllib.error
from collections import defaultdict

# Config
GITHUB_TOKEN = os.environ.get("GH_TOKEN", "").strip()
TOP_N = 10
OUTPUT_FILE = "radar.svg"

TOKYO_COLORS = [
    "#7aa2f7",
    "#bb9af7",
    "#7dcfff",
    "#73daca",
    "#9ece6a",
    "#e0af68",
    "#f7768e",
    "#ff9e64",
    "#b4f9f8",
    "#c0caf5",
]

TOKYO = {
    "bg": "#1a1b2e",
    "bg_dark": "#16161e",
    "bg_panel": "#1f2335",
    "border": "#3b4261",
    "comment": "#565f89",
    "fg": "#c0caf5",
    "fg_dim": "#a9b1d6",
    "fg_dark": "#9aa5ce",
    "accent": "#7aa2f7",
}


def gh_request(url):
    req = urllib.request.Request(url)

    if GITHUB_TOKEN:
        req.add_header("Authorization", f"Bearer {GITHUB_TOKEN}")

    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "tech-radar-generator/1.0")

    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub API hatası: HTTP {e.code}\nURL: {url}\nYanıt: {body}"
        ) from e


def fetch_all_repos():
    repos = []
    page = 1

    while True:
        url = (
            "https://api.github.com/user/repos"
            f"?per_page=100&page={page}"
            "&visibility=all"
            "&affiliation=owner,collaborator,organization_member"
            "&sort=updated"
            "&direction=desc"
        )

        batch = gh_request(url)

        if not batch:
            break

        repos.extend(batch)

        if len(batch) < 100:
            break

        page += 1

    return repos


def fetch_languages(repo_full_name):
    try:
        return gh_request(f"https://api.github.com/repos/{repo_full_name}/languages")
    except RuntimeError as e:
        print(f"  Uyarı: {repo_full_name} dil verisi alınamadı.")
        print(f"  {e}")
        return {}


def get_top_languages():
    if not GITHUB_TOKEN:
        raise RuntimeError(
            "GH_TOKEN bulunamadı. GitHub repo listesini çekmek için secrets.GH_TOKEN gerekli."
        )

    repos = fetch_all_repos()
    print(f"  {len(repos)} repo bulundu.")

    totals = defaultdict(int)

    for repo in repos:
        full_name = repo.get("full_name")

        if not full_name:
            continue

        langs = fetch_languages(full_name)

        for lang, byte_count in langs.items():
            totals[lang] += byte_count

    sorted_langs = sorted(totals.items(), key=lambda x: x[1], reverse=True)
    top = sorted_langs[:TOP_N]

    if not top:
        return []

    max_val = top[0][1]

    return [(lang, round(val / max_val * 100)) for lang, val in top]


def polar(angle_deg, radius, cx, cy):
    rad = math.radians(angle_deg - 90)
    return round(cx + radius * math.cos(rad), 2), round(cy + radius * math.sin(rad), 2)


def polygon_pts(values, max_r, cx, cy, n):
    pts = []

    for i, v in enumerate(values):
        x, y = polar(360 / n * i, v / 100 * max_r, cx, cy)
        pts.append(f"{x},{y}")

    return " ".join(pts)


def generate_svg(languages):
    n = len(languages)
    w, h = 520, 500
    cx, cy = 260, 242
    max_r = 170
    rings = 4

    color_map = {
        lang: TOKYO_COLORS[i % len(TOKYO_COLORS)]
        for i, (lang, _) in enumerate(languages)
    }

    out = []

    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
    )

    out.append(
        """  <defs>
    <filter id="glow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur in="SourceGraphic" stdDeviation="3" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
    <filter id="softglow" x="-20%" y="-20%" width="140%" height="140%">
      <feGaussianBlur in="SourceGraphic" stdDeviation="1.5" result="blur"/>
      <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
    </filter>
  </defs>"""
    )

    out.append(f'  <rect width="{w}" height="{h}" fill="{TOKYO["bg"]}" rx="12"/>')
    out.append(
        f'  <rect x="1" y="1" width="{w - 2}" height="{h - 2}" fill="none" stroke="{TOKYO["border"]}" stroke-width="1" rx="11"/>'
    )

    out.append(
        f'  <text x="{cx}" y="28" text-anchor="middle" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,monospace" font-size="15" font-weight="700" fill="{TOKYO["accent"]}" filter="url(#softglow)">Tech Radar</text>'
    )
    out.append(
        f'  <text x="{cx}" y="44" text-anchor="middle" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" font-size="10" fill="{TOKYO["comment"]}">top {n} languages across all repos</text>'
    )

    out.append(
        f'  <circle cx="{cx}" cy="{cy}" r="{max_r + 10}" fill="{TOKYO["bg_panel"]}" opacity="0.5"/>'
    )

    for i in range(1, rings + 1):
        r = max_r * i / rings
        pts = []

        for j in range(n):
            x, y = polar(360 / n * j, r, cx, cy)
            pts.append(f"{x},{y}")

        opacity = 0.5 if i < rings else 0.8

        out.append(
            f'  <polygon points="{" ".join(pts)}" fill="none" stroke="{TOKYO["border"]}" stroke-width="0.8" opacity="{opacity}"/>'
        )

    for i in range(n):
        x_end, y_end = polar(360 / n * i, max_r, cx, cy)
        out.append(
            f'  <line x1="{cx}" y1="{cy}" x2="{x_end}" y2="{y_end}" stroke="{TOKYO["border"]}" stroke-width="0.8" opacity="0.6"/>'
        )

    vals = [pct for _, pct in languages]
    poly = polygon_pts(vals, max_r, cx, cy, n)

    out.append(
        f'  <polygon points="{poly}" fill="{TOKYO["accent"]}" fill-opacity="0.12" stroke="{TOKYO["accent"]}" stroke-width="1.8" filter="url(#softglow)"/>'
    )

    for i, (lang, pct) in enumerate(languages):
        angle = 360 / n * i
        color = color_map[lang]

        dx, dy = polar(angle, pct / 100 * max_r, cx, cy)

        out.append(
            f'  <circle cx="{dx}" cy="{dy}" r="5" fill="{color}" stroke="{TOKYO["bg"]}" stroke-width="1.5" filter="url(#glow)"/>'
        )

        lx, ly = polar(angle, max_r + 48, cx, cy)

        if abs(lx - cx) < 10:
            anchor = "middle"
        elif lx < cx:
            anchor = "end"
        else:
            anchor = "start"

        out.append(
            f'  <text x="{lx}" y="{ly - 6}" text-anchor="{anchor}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,monospace" font-size="12" font-weight="600" fill="{color}" filter="url(#softglow)">{lang}</text>'
        )
        out.append(
            f'  <text x="{lx}" y="{ly + 8}" text-anchor="{anchor}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" font-size="10" fill="{TOKYO["comment"]}">{pct}%</text>'
        )

    out.append(f'  <circle cx="{cx}" cy="{cy}" r="3" fill="{TOKYO["border"]}"/>')

    out.append(
        f'  <text x="{cx}" y="{h - 12}" text-anchor="middle" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" font-size="9" fill="{TOKYO["comment"]}">auto-generated daily</text>'
    )

    out.append("</svg>")

    return "\n".join(out)


if __name__ == "__main__":
    print("GitHub API'dan dil verileri çekiliyor...")

    langs = get_top_languages()

    if not langs:
        print("Hiç dil verisi bulunamadı. Token ve repo izinlerini kontrol et.")
        raise SystemExit(1)

    print(f"\nTop {len(langs)} dil:")

    for lang, pct in langs:
        bar = "#" * (pct // 5) + "." * (20 - pct // 5)
        print(f"  {lang:<16} {pct:>3}%  {bar}")

    svg = generate_svg(langs)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(svg)

    print(f"\nKaydedildi: {OUTPUT_FILE}")

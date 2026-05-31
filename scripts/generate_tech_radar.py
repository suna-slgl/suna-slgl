
import os
import requests
import numpy as np
import matplotlib.pyplot as plt
from collections import Counter

TOKEN = os.getenv("GH_TOKEN")

if not TOKEN:
    raise RuntimeError("GH_TOKEN secret is missing")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
}

THEME = {
    "background": "#1a1b27",
    "grid": "#414868",
    "text": "#c0caf5",
    "primary": "#7aa2f7",
}


def github_get(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def get_repositories():
    repos = []
    page = 1

    while True:
        data = github_get(
            f"https://api.github.com/user/repos"
            f"?visibility=all&affiliation=owner"
            f"&per_page=100&page={page}"
        )

        if not data:
            break

        repos.extend(data)
        page += 1

    return repos


def collect_languages():
    scores = Counter()

    repos = get_repositories()

    for repo in repos:

        if repo.get("fork"):
            continue

        try:
            langs = github_get(
                f"https://api.github.com/repos/"
                f"{repo['full_name']}/languages"
            )

            for language, bytes_used in langs.items():
                scores[language] += bytes_used

        except Exception:
            continue

    return scores


def normalize_scores(scores, top_n=10):

    if not scores:
        return {
            "Python": 10,
            "Dart": 8,
            "TypeScript": 6
        }

    top = scores.most_common(top_n)

    max_score = max(v for _, v in top)

    return {
        k: round((v / max_score) * 10, 1)
        for k, v in top
    }


def create_radar(data):

    labels = list(data.keys())
    values = list(data.values())

    angles = np.linspace(
        0,
        2 * np.pi,
        len(labels),
        endpoint=False
    ).tolist()

    labels.append(labels[0])
    values.append(values[0])
    angles.append(angles[0])

    fig = plt.figure(
        figsize=(8, 8),
        facecolor=THEME["background"]
    )

    ax = plt.subplot(111, polar=True)

    ax.set_facecolor(
        THEME["background"]
    )

    ax.plot(
        angles,
        values,
        color=THEME["primary"],
        linewidth=2.5
    )

    ax.fill(
        angles,
        values,
        color=THEME["primary"],
        alpha=0.25
    )

    ax.set_xticks(angles[:-1])

    ax.set_xticklabels(
        labels[:-1],
        color=THEME["text"],
        fontsize=11
    )

    ax.tick_params(
        colors=THEME["text"]
    )

    ax.grid(
        color=THEME["grid"],
        alpha=0.6
    )

    ax.spines["polar"].set_color(
        THEME["grid"]
    )

    ax.set_ylim(0, 10)

    ax.set_title(
        "Tech Radar",
        color=THEME["text"],
        fontsize=18,
        pad=20
    )

    os.makedirs(
        "assets",
        exist_ok=True
    )

    plt.savefig(
        "assets/tech-radar.svg",
        format="svg",
        bbox_inches="tight",
        facecolor=THEME["background"]
    )


if __name__ == "__main__":

    scores = collect_languages()

    radar = normalize_scores(
        scores,
        top_n=10
    )

    create_radar(radar)

    print(radar)

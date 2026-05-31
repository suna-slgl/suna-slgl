import os
import re
import requests
import numpy as np
import matplotlib.pyplot as plt
from collections import Counter

USERNAME = os.getenv("GITHUB_USERNAME", "suna-slgl")
TOKEN = os.getenv("GH_TOKEN")

if not TOKEN:
    raise RuntimeError("GH_TOKEN secret is missing.")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/vnd.github+json",
}

TECH_KEYWORDS = {
    "Python": ["python", ".py", "fastapi", "flask", "django"],
    "Dart": ["dart", ".dart"],
    "Flutter": ["flutter", "pubspec.yaml"],
    "JavaScript": ["javascript", ".js", "node", "express"],
    "TypeScript": ["typescript", ".ts", ".tsx"],
    "Firebase": ["firebase", "firestore", "firebase.json"],
    "Computer Vision": ["opencv", "yolo", "resnet", "torchvision", "cv2"],
    "NLP": ["spacy", "nltk", "transformers", "bert", "nlp"],
    "SQL": ["sql", "postgres", "mysql", "sqlite"],
    "HTML/CSS": ["html", "css", ".html", ".css"],
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
        url = f"https://api.github.com/user/repos?visibility=all&affiliation=owner&per_page=100&page={page}"
        data = github_get(url)

        if not data:
            break

        repos.extend(data)
        page += 1

    return repos

def get_repo_languages(repo_full_name):
    url = f"https://api.github.com/repos/{repo_full_name}/languages"
    return github_get(url)

def get_repo_text(repo_full_name):
    files = [
        "README.md",
        "requirements.txt",
        "pyproject.toml",
        "package.json",
        "pubspec.yaml",
        "firebase.json",
        "Dockerfile",
    ]

    text = ""

    for file_path in files:
        url = f"https://api.github.com/repos/{repo_full_name}/contents/{file_path}"
        r = requests.get(url, headers=HEADERS, timeout=30)

        if r.status_code != 200:
            continue

        data = r.json()
        download_url = data.get("download_url")

        if not download_url:
            continue

        raw = requests.get(download_url, headers=HEADERS, timeout=30)

        if raw.status_code == 200:
            text += "\n" + raw.text.lower()

    return text

def score_technologies():
    repos = get_repositories()
    scores = Counter()

    for repo in repos:
        if repo.get("fork"):
            continue

        full_name = repo["full_name"]
        repo_name = repo["name"].lower()
        description = (repo.get("description") or "").lower()

        languages = get_repo_languages(full_name)
        repo_text = get_repo_text(full_name)

        searchable = f"{repo_name}\n{description}\n{repo_text}"

        for language, byte_count in languages.items():
            if language in TECH_KEYWORDS:
                scores[language] += max(1, byte_count // 1000)

        for tech, keywords in TECH_KEYWORDS.items():
            for keyword in keywords:
                if re.search(re.escape(keyword.lower()), searchable):
                    scores[tech] += 5

    return scores

def normalize_scores(scores, max_items=8):
    if not scores:
        return {
            "Python": 1,
            "Dart": 1,
            "Flutter": 1,
            "Firebase": 1,
            "Computer Vision": 1,
            "NLP": 1,
        }

    selected = scores.most_common(max_items)
    max_score = max(score for _, score in selected)

    return {
        tech: max(1, round((score / max_score) * 10))
        for tech, score in selected
    }

def create_radar_chart(data):
    labels = list(data.keys())
    values = list(data.values())

    values += values[:1]

    angles = np.linspace(0, 2 * np.pi, len(labels), endpoint=False).tolist()
    angles += angles[:1]

    plt.figure(figsize=(7, 7), facecolor=THEME["background"])
    ax = plt.subplot(111, polar=True)
    ax.set_facecolor(THEME["background"])

    ax.plot(angles, values, linewidth=2, color=THEME["primary"])
    ax.fill(angles, values, alpha=0.25, color=THEME["primary"])

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(labels, color=THEME["text"], fontsize=11)

    ax.set_yticks([2, 4, 6, 8, 10])
    ax.set_yticklabels(["2", "4", "6", "8", "10"], color=THEME["grid"], fontsize=9)
    ax.set_ylim(0, 10)

    ax.spines["polar"].set_color(THEME["grid"])
    ax.grid(color=THEME["grid"], alpha=0.6)

    ax.set_title(
        "Tech Radar",
        color=THEME["text"],
        fontsize=18,
        fontweight="bold",
        pad=24,
    )

    os.makedirs("assets", exist_ok=True)

    plt.savefig(
        "assets/tech-radar.svg",
        format="svg",
        facecolor=THEME["background"],
        bbox_inches="tight",
    )

if __name__ == "__main__":
    scores = score_technologies()
    radar_data = normalize_scores(scores)
    create_radar_chart(radar_data)

import os
import re
import json
import requests
import numpy as np
import matplotlib.pyplot as plt
from collections import Counter

TOKEN = os.getenv("GH_TOKEN")

if not TOKEN:
    raise RuntimeError("GH_TOKEN secret is missing.")

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

TECH_NORMALIZATION = {
    # Languages
    "python": "Python",
    "dart": "Dart",
    "typescript": "TypeScript",
    "javascript": "JavaScript",

    # Flutter
    "flutter": "Flutter",

    # Backend
    "fastapi": "FastAPI",
    "django": "Django",
    "flask": "Flask",

    # Firebase
    "firebase": "Firebase",
    "firebase_core": "Firebase",
    "firebase_auth": "Firebase",
    "cloud_firestore": "Firebase",
    "firestore": "Firebase",

    # CV
    "opencv": "OpenCV",
    "opencv-python": "OpenCV",
    "opencv-contrib-python": "OpenCV",
    "cv2": "OpenCV",

    "ultralytics": "YOLO",
    "yolo": "YOLO",
    "yolov8": "YOLO",

    "torch": "PyTorch",
    "torchvision": "PyTorch",

    # NLP
    "spacy": "spaCy",
    "transformers": "Transformers",
    "sentence-transformers": "Transformers",
    "bert": "Transformers",

    # Databases
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "mysql": "MySQL",
    "sqlite": "SQLite",
    "sqlalchemy": "SQLAlchemy",

    # JS ecosystem
    "react": "React",
    "next": "Next.js",
    "node": "Node.js",
    "express": "Express",

    # DevOps
    "docker": "Docker",
    "kubernetes": "Kubernetes",
}


def github_get(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return r.json()


def get_repositories():
    repos = []
    page = 1

    while True:
        url = (
            "https://api.github.com/user/repos"
            f"?visibility=all&affiliation=owner&per_page=100&page={page}"
        )

        data = github_get(url)

        if not data:
            break

        repos.extend(data)
        page += 1

    return repos


def get_repo_languages(full_name):
    try:
        return github_get(
            f"https://api.github.com/repos/{full_name}/languages"
        )
    except:
        return {}


def get_file_content(full_name, path):
    try:
        data = github_get(
            f"https://api.github.com/repos/{full_name}/contents/{path}"
        )

        download_url = data.get("download_url")

        if not download_url:
            return ""

        r = requests.get(download_url, headers=HEADERS, timeout=30)

        if r.status_code == 200:
            return r.text.lower()

    except:
        pass

    return ""


def collect_repo_text(full_name):
    files = [
        "README.md",
        "requirements.txt",
        "pyproject.toml",
        "package.json",
        "pubspec.yaml",
        "firebase.json",
        "Dockerfile",
    ]

    combined = ""

    for file in files:
        combined += "\n" + get_file_content(full_name, file)

    return combined.lower()


def score_languages(scores, languages):
    total_bytes = sum(languages.values())

    if total_bytes == 0:
        return

    for language, bytes_used in languages.items():
        normalized = language.lower()

        if normalized not in TECH_NORMALIZATION:
            continue

        tech = TECH_NORMALIZATION[normalized]

        percentage = bytes_used / total_bytes

        scores[tech] += percentage * 40


def score_dependencies(scores, text):
    for keyword, tech in TECH_NORMALIZATION.items():

        matches = len(
            re.findall(
                rf"\b{re.escape(keyword.lower())}\b",
                text
            )
        )

        if matches:
            scores[tech] += matches * 8


def analyze_repositories():
    repos = get_repositories()
    scores = Counter()

    for repo in repos:

        if repo.get("fork"):
            continue

        full_name = repo["full_name"]

        description = (
            repo.get("description") or ""
        ).lower()

        languages = get_repo_languages(full_name)

        score_languages(scores, languages)

        text = collect_repo_text(full_name)

        searchable = f"{description}\n{text}"

        score_dependencies(scores, searchable)

    return scores


def normalize_scores(scores, top_n=10):

    if not scores:
        return {
            "Python": 10,
            "Flutter": 8,
            "FastAPI": 7,
        }

    selected = scores.most_common(top_n)

    max_score = max(v for _, v in selected)

    return {
        tech: round((score / max_score) * 10, 1)
        for tech, score in selected
    }


def create_radar_chart(data):

    labels = list(data.keys())
    values = list(data.values())

    labels += labels[:1]
    values += values[:1]

    angles = np.linspace(
        0,
        2 * np.pi,
        len(labels),
        endpoint=False
    ).tolist()

    angles += angles[:1]

    plt.figure(
        figsize=(8, 8),
        facecolor=THEME["background"]
    )

    ax = plt.subplot(111, polar=True)

    ax.set_facecolor(THEME["background"])

    ax.plot(
        angles,
        values,
        linewidth=2.5,
        color=THEME["primary"]
    )

    ax.fill(
        angles,
        values,
        alpha=0.25,
        color=THEME["primary"]
    )

    ax.set_xticks(angles[:-1])

    ax.set_xticklabels(
        labels[:-1],
        color=THEME["text"],
        fontsize=11
    )

    ax.set_ylim(0, 10)

    ax.grid(
        color=THEME["grid"],
        alpha=0.6
    )

    ax.spines["polar"].set_color(
        THEME["grid"]
    )

    ax.set_title(
        "Tech Radar",
        color=THEME["text"],
        fontsize=18,
        fontweight="bold",
        pad=25,
    )

    os.makedirs(
        "assets",
        exist_ok=True
    )

    plt.savefig(
        "assets/tech-radar.svg",
        format="svg",
        facecolor=THEME["background"],
        bbox_inches="tight"
    )


if __name__ == "__main__":

    scores = analyze_repositories()

    radar = normalize_scores(
        scores,
        top_n=10
    )

    create_radar_chart(radar)

    print(radar)

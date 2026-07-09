import base64
import html
import json
import math
import os
import re
import tomllib
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter


GITHUB_TOKEN = os.environ.get("GH_TOKEN", "").strip()
TOP_N = int(os.environ.get("TOP_N", "10"))
OUTPUT_FILE = os.environ.get("OUTPUT_FILE", "assets/tech-radar.svg")

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
    "grid": "#629cf4",
    "comment": "#565f89",
    "fg": "#c0caf5",
    "accent": "#29bda3",
    "label": "#b482ee",
}

MANIFEST_FILES = (
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "Pipfile",
    "pubspec.yaml",
    "Cargo.toml",
    "go.mod",
    "composer.json",
    "Gemfile",
)

TECH_ALIASES = {
    "@angular/core": "Angular",
    "@nestjs/core": "NestJS",
    "@reduxjs/toolkit": "Redux",
    "@tailwindcss/vite": "Tailwind CSS",
    "@vitejs/plugin-react": "Vite",
    "@vitejs/plugin-vue": "Vite",
    "asp.net": "ASP.NET",
    "asp.net-core": "ASP.NET Core",
    "aspnetcore": "ASP.NET Core",
    "batchfile": "Batch",
    "bootstrap": "Bootstrap",
    "csharp": "C#",
    "css3": "CSS",
    "cv2": "OpenCV",
    "docker": "Docker",
    "docker-compose": "Docker",
    "dockerfile": "Docker",
    "django": "Django",
    "dotenv": "Dotenv",
    "ecmascript": "JavaScript",
    "eslint": "ESLint",
    "express": "Express",
    "fastapi": "FastAPI",
    "firebase": "Firebase",
    "flask": "Flask",
    "flutter": "Flutter",
    "github-actions": "GitHub Actions",
    "go-mod": "Go",
    "golang": "Go",
    "graphql": "GraphQL",
    "html5": "HTML",
    "ipynb": "Jupyter",
    "javascript": "JavaScript",
    "jquery": "jQuery",
    "jupyter": "Jupyter",
    "jupyter-notebook": "Jupyter",
    "laravel": "Laravel",
    "makefile": "Make",
    "matplotlib": "Matplotlib",
    "mdx": "MDX",
    "mongodb": "MongoDB",
    "mongoose": "Mongoose",
    "mysql": "MySQL",
    "next": "Next.js",
    "next.js": "Next.js",
    "node": "Node.js",
    "node.js": "Node.js",
    "numpy": "NumPy",
    "opencv": "OpenCV",
    "opencv-python": "OpenCV",
    "opencv-python-headless": "OpenCV",
    "opencv-contrib-python": "OpenCV",
    "opencv-contrib-python-headless": "OpenCV",
    "pandas": "Pandas",
    "powershell": "PowerShell",
    "postgres": "PostgreSQL",
    "postgresql": "PostgreSQL",
    "prisma": "Prisma",
    "ps1": "PowerShell",
    "pytest": "Pytest",
    "python": "Python",
    "react": "React",
    "react-dom": "React",
    "react-native": "React Native",
    "redis": "Redis",
    "sass": "Sass",
    "scikit-learn": "Scikit-learn",
    "scss": "Sass",
    "sh": "Shell",
    "shell-script": "Shell",
    "spring": "Spring",
    "spring-boot": "Spring Boot",
    "sqlite": "SQLite",
    "tailwind": "Tailwind CSS",
    "tailwindcss": "Tailwind CSS",
    "tensorflow": "TensorFlow",
    "ts": "TypeScript",
    "tsx": "TypeScript",
    "typescript": "TypeScript",
    "vite": "Vite",
    "vue": "Vue",
    "vue.js": "Vue",
}


def normalize(name):
    raw = name.strip()
    key = raw.lower().replace("_", "-").replace(" ", "-")

    if key.startswith("@types/") or key.startswith("@types-"):
        return "TypeScript"

    if key.startswith("@vitejs/"):
        return "Vite"

    if key.startswith("@tailwindcss/") or key.startswith("tailwindcss-"):
        return "Tailwind CSS"

    if key.startswith("eslint-") or key.startswith("@eslint/"):
        return "ESLint"

    if key.startswith("prettier-") or key.startswith("@prettier/"):
        return "Prettier"

    if key.startswith("babel-") or key.startswith("@babel/"):
        return "Babel"

    if key.startswith("jest-") or key.startswith("@jest/"):
        return "Jest"

    if key.startswith("flask-"):
        return "Flask"

    if key.startswith("django-"):
        return "Django"

    if key.startswith("docker-"):
        return "Docker"

    if key.startswith("next-"):
        return "Next.js"

    if key.startswith("opencv-"):
        return "OpenCV"

    if key.startswith("react-") and key != "react-native":
        return "React"

    return TECH_ALIASES.get(key, raw)


def deduplicate_names(names):
    unique = {}

    for name in names:
        key = name.casefold()
        current = unique.get(key)

        if current is None or (current.islower() and not name.islower()):
            unique[key] = name

    return unique


def gh_request(url, *, accept="application/vnd.github+json", allow_404=False):
    req = urllib.request.Request(url)

    if GITHUB_TOKEN:
        req.add_header("Authorization", f"Bearer {GITHUB_TOKEN}")

    req.add_header("Accept", accept)
    req.add_header("X-GitHub-Api-Version", "2022-11-28")
    req.add_header("User-Agent", "tech-radar-generator/2.0")

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        if allow_404 and error.code == 404:
            return None

        body = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"GitHub API error: HTTP {error.code}\nURL: {url}\nResponse: {body}"
        ) from error


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
    return gh_request(f"https://api.github.com/repos/{repo_full_name}/languages")


def fetch_manifest(repo_full_name, path):
    encoded_path = urllib.parse.quote(path)
    url = f"https://api.github.com/repos/{repo_full_name}/contents/{encoded_path}"
    data = gh_request(url, allow_404=True)

    if not data or data.get("type") != "file" or data.get("encoding") != "base64":
        return ""

    content = data.get("content", "")
    return base64.b64decode(content).decode("utf-8", errors="replace")


def extract_package_json_tech(content):
    techs = set()

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return techs

    for section in (
        "dependencies",
        "devDependencies",
        "peerDependencies",
        "optionalDependencies",
    ):
        for package_name in data.get(section, {}):
            techs.add(normalize(package_name))

    return techs


def extract_requirements_tech(content):
    techs = set()

    for line in content.splitlines():
        clean = line.strip()

        if not clean or clean.startswith(("#", "[", ";")):
            continue

        name = clean.split("==")[0].split(">=")[0].split("<=")[0].split("~=")[0]
        name = name.split("=")[0].split("[")[0].strip()

        if name:
            techs.add(normalize(name))

    return techs


def extract_toml_tech(content, sections):
    techs = set()

    try:
        data = tomllib.loads(content)
    except tomllib.TOMLDecodeError:
        return techs

    for section in sections:
        current = data

        for key in section:
            current = current.get(key, {})

            if not isinstance(current, (dict, list)):
                current = {}
                break

        if isinstance(current, dict):
            for name, value in current.items():
                if name.lower() == "python":
                    continue

                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, str):
                            package = re.split(r"[<>=~!;\[]", item, maxsplit=1)[
                                0
                            ].strip()

                            if package:
                                techs.add(normalize(package))
                else:
                    techs.add(normalize(name))
        elif isinstance(current, list):
            for item in current:
                if isinstance(item, str):
                    name = re.split(r"[<>=~!;\[]", item, maxsplit=1)[0].strip()

                    if name:
                        techs.add(normalize(name))

    return techs


def extract_pubspec_tech(content):
    techs = set()
    active = False

    for line in content.splitlines():
        if re.match(r"^(dependencies|dev_dependencies):\s*$", line):
            active = True
            continue

        if active and line and not line.startswith((" ", "\t")):
            active = False

        if not active:
            continue

        match = re.match(r"^\s{2,}([A-Za-z0-9_\-]+):", line)

        if match and match.group(1) != "sdk":
            techs.add(normalize(match.group(1)))

    return techs


def extract_go_mod_tech(content):
    techs = set()

    for line in content.splitlines():
        clean = line.strip()

        if clean.startswith("require "):
            package = clean.replace("require ", "", 1).split()[0]
        elif clean and not clean.startswith(("//", "module", "go", "replace", "(")):
            package = clean.split()[0]
        else:
            continue

        techs.add(normalize(package.split("/")[-1]))

    return techs


def extract_composer_tech(content):
    techs = set()

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return techs

    for section in ("require", "require-dev"):
        for package_name in data.get(section, {}):
            techs.add(normalize(package_name.split("/")[-1]))

    return techs


def extract_gemfile_tech(content):
    techs = set()

    for line in content.splitlines():
        match = re.match(r"^\s*gem\s+['\"]([^'\"]+)['\"]", line)

        if match:
            techs.add(normalize(match.group(1)))

    return techs


def extract_manifest_tech(path, content):
    if path == "package.json":
        return extract_package_json_tech(content)

    if path == "requirements.txt":
        return extract_requirements_tech(content)

    if path == "pyproject.toml":
        return extract_toml_tech(
            content,
            (
                ("project", "dependencies"),
                ("project", "optional-dependencies"),
                ("tool", "poetry", "dependencies"),
                ("tool", "poetry", "group", "dev", "dependencies"),
            ),
        )

    if path == "Pipfile":
        return extract_toml_tech(content, (("packages",), ("dev-packages",)))

    if path == "pubspec.yaml":
        return extract_pubspec_tech(content)

    if path == "Cargo.toml":
        return extract_toml_tech(content, (("dependencies",), ("dev-dependencies",)))

    if path == "go.mod":
        return extract_go_mod_tech(content)

    if path == "composer.json":
        return extract_composer_tech(content)

    if path == "Gemfile":
        return extract_gemfile_tech(content)

    return set()


def collect_repo_technologies(repo):
    full_name = repo.get("full_name")
    repo_techs = set()

    if not full_name:
        return repo_techs

    try:
        repo_techs.update(normalize(lang) for lang in fetch_languages(full_name))
    except RuntimeError as error:
        print(f"  Warning: could not fetch languages for {full_name}: {error}")

    for manifest in MANIFEST_FILES:
        try:
            content = fetch_manifest(full_name, manifest)
        except RuntimeError as error:
            print(f"  Warning: could not fetch {manifest} for {full_name}: {error}")
            continue

        if content:
            repo_techs.update(extract_manifest_tech(manifest, content))

    return set(deduplicate_names(tech for tech in repo_techs if tech).values())


def get_top_technologies():
    if not GITHUB_TOKEN:
        raise RuntimeError(
            "GH_TOKEN is required. Add a classic PAT or fine-grained token with access to public and private repositories."
        )

    repos = fetch_all_repos()
    print(f"  Found {len(repos)} repositories.")

    totals = Counter()
    display_names = {}
    repository_count = 0

    for repo in repos:
        if repo.get("archived"):
            continue

        repository_count += 1
        repo_techs = deduplicate_names(collect_repo_technologies(repo)).values()
        for tech in repo_techs:
            key = tech.casefold()
            totals[key] += 1

            current = display_names.get(key)

            if current is None or (current.islower() and not tech.islower()):
                display_names[key] = tech

    top = totals.most_common(TOP_N)

    if not top:
        return []

    # max_count = top[0][1]
    # percentage = round(count / max_count * 100)
    return [
        (display_names[key], count, round(count / repository_count * 100))
        for key, count in top
    ]


def polar(angle_deg, radius, cx, cy):
    rad = math.radians(angle_deg - 90)
    return round(cx + radius * math.cos(rad), 2), round(cy + radius * math.sin(rad), 2)


def polygon_points(items, max_percentage, max_r, cx, cy):
    points = []
    total = len(items)

    for index, (_, _, pct) in enumerate(items):
        x, y = polar(360 / total * index, pct / max_percentage * max_r, cx, cy)
        points.append(f"{x},{y}")

    return " ".join(points)


def generate_svg(items):
    total = len(items)
    width, height = 760, 680
    cx, cy = 380, 340
    max_r = 235
    rings = (25, 50, 75, 100)
    max_percentage = max(1, min(100, max(pct for _, _, pct in items) * 1.1))

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="Top {total} technologies radar chart">',
        "  <defs>",
        '    <filter id="softglow" x="-25%" y="-25%" width="150%" height="150%">',
        '      <feGaussianBlur in="SourceGraphic" stdDeviation="1.8" result="blur"/>',
        "      <feMerge><feMergeNode in=\"blur\"/><feMergeNode in=\"SourceGraphic\"/></feMerge>",
        "    </filter>",
        "  </defs>",
    ]

    for pct in rings:
        radius = max_r * pct / 100
        points = []

        for index in range(total):
            x, y = polar(360 / total * index, radius, cx, cy)
            points.append(f"{x},{y}")

        opacity = 0.35 if pct < 100 else 0.75
        out.append(
            f'  <polygon points="{" ".join(points)}" fill="none" stroke="{TOKYO["grid"]}" stroke-width="0.9" opacity="{opacity}"/>'
        )

        label_x, label_y = polar(180, radius, cx, cy)
        ring_percentage = max_percentage * pct / 100
        ring_label = f"{ring_percentage:.1f}".rstrip("0").rstrip(".")
        out.append(
            f'  <text x="{label_x + 8}" y="{label_y + 4}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif" font-size="10" fill="{TOKYO["fg"]}" opacity="0.82">{ring_label}%</text>'
        )

    for index in range(total):
        x_end, y_end = polar(360 / total * index, max_r, cx, cy)
        out.append(
            f'  <line x1="{cx}" y1="{cy}" x2="{x_end}" y2="{y_end}" stroke="{TOKYO["grid"]}" stroke-width="0.8" opacity="0.38"/>'
        )

    out.append(
        f'  <polygon points="{polygon_points(items, max_percentage, max_r, cx, cy)}" fill="{TOKYO["accent"]}" fill-opacity="0.26" stroke="{TOKYO["accent"]}" stroke-width="2.4" filter="url(#softglow)"/>'
    )

    for index, (name, count, pct) in enumerate(items):
        angle = 360 / total * index
        dot_x, dot_y = polar(angle, pct / max_percentage * max_r, cx, cy)
        label_x, label_y = polar(angle, max_r + 58, cx, cy)

        if abs(label_x - cx) < 12:
            anchor = "middle"
        elif label_x < cx:
            anchor = "end"
        else:
            anchor = "start"

        safe_name = html.escape(name)
        out.append(
            f'  <circle cx="{dot_x}" cy="{dot_y}" r="4.5" fill="{TOKYO["accent"]}" stroke="{TOKYO["accent"]}" stroke-width="1" filter="url(#softglow)"/>'
        )
        out.append(
            f'  <text x="{label_x}" y="{label_y - 3}" text-anchor="{anchor}" font-family="-apple-system,BlinkMacSystemFont,Segoe UI,monospace" font-size="12" font-weight="700" fill="{TOKYO["label"]}">{safe_name}</text>'
        )

    out.extend(
        [
            f'  <circle cx="{cx}" cy="{cy}" r="3" fill="{TOKYO["grid"]}" opacity="0.75"/>',
            "</svg>",
        ]
    )

    return "\n".join(out)


if __name__ == "__main__":
    print("Fetching repository technologies from GitHub API...")

    technologies = get_top_technologies()

    if not technologies:
        print("No technologies found. Check token permissions and repository access.")
        raise SystemExit(1)

    print(f"\nTop {len(technologies)} technologies:")

    for name, count, pct in technologies:
        bar = "#" * max(1, pct // 5)
        print(f"  {name:<20} {count:>3} repos  {bar}")

    os.makedirs(os.path.dirname(OUTPUT_FILE) or ".", exist_ok=True)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        file.write(generate_svg(technologies))

    print(f"\nSaved: {OUTPUT_FILE}")

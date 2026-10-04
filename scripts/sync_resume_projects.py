#!/usr/bin/env python3
import json
import re
import sys
import unicodedata
from pathlib import Path

import fitz


ROOT = Path(__file__).resolve().parents[1]
RESUME_PATH = ROOT / "client/public/Rewa-Prasad-Resume.pdf"
PROFILE_PATH = ROOT / "client/public/profile.json"
PROJECTS_START = {"PROJECTS", "PROJECTS & EXPERIENCE", "PROJECT EXPERIENCE"}
NON_PROJECT_SECTION_HEADINGS = (
    "TECHNICAL SKILLS",
    "CERTIFICATIONS",
    "CERTIFICATION",
    "LANGUAGES",
    "EDUCATION",
    "EXPERIENCE",
    "SKILLS",
    "AWARDS",
    "SUMMARY",
    "PROFILE",
)
NON_PROJECT_SECTION_PATTERN = re.compile(
    r"\b(?:"
    + "|".join(re.escape(heading) for heading in NON_PROJECT_SECTION_HEADINGS)
    + r")\b"
)
INVISIBLE = re.compile(r"[\u200b-\u200f\ufeff]")
RESUME_URL = re.compile(r"https?://[^\s)]+", re.IGNORECASE)
NUMBERED_PROJECT = re.compile(r"^#\s*\d+\s*[:.)-]\s*(.+)$")
BULLET = re.compile(r"^[○◦o·]\s*(.*)$")
TOP_LEVEL = re.compile(r"^[●•·]\s*(.+)$")
DATE_RANGE = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
    r"\s+\d{4}\s*[-–]\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"[a-z]*\s+)?(?:\d{4}|Present)\b",
    re.IGNORECASE,
)


def clean(value):
    value = unicodedata.normalize("NFKC", value)
    value = INVISIBLE.sub("", value)
    return re.sub(r"\s+", " ", value).strip()


def extract_project_section(pdf_path):
    document = fitz.open(pdf_path)
    lines = [
        clean(line)
        for page in document
        for line in page.get_text("text").splitlines()
    ]
    document.close()

    start = next(
        (index for index, line in enumerate(lines) if line.upper() in PROJECTS_START),
        None,
    )
    if start is None:
        raise ValueError("Could not find the PROJECTS section in the resume PDF.")

    # Some resume templates place a sidebar section (such as Skills) below
    # Projects on page one, then continue Projects at the top of page two.
    return [line for line in lines[start + 1 :] if line]


def append_description(target, value):
    value = clean(value).strip(" •·")
    if not value:
        return
    if target["achievements"]:
        target["achievements"][-1] = f'{target["achievements"][-1]} {value}'
    else:
        target["achievements"].append(value)


def parse_project_section(lines):
    projects = []
    current = None
    personal_stack = []
    in_personal_section = False
    in_non_project_section = False
    awaiting_bullet_text = False

    def finish():
        nonlocal current, awaiting_bullet_text
        if current and current["name"]:
            current["achievements"] = [
                re.sub(r"\s+", " ", point).strip()
                for point in current["achievements"]
                if point.strip()
            ]
            projects.append(current)
        current = None
        awaiting_bullet_text = False

    for line in lines:
        section_match = NON_PROJECT_SECTION_PATTERN.search(line)
        if section_match:
            line = clean(line[: section_match.start()])
            in_non_project_section = True
            if not line:
                continue

        top_level = TOP_LEVEL.match(line)
        numbered = NUMBERED_PROJECT.match(line)
        bullet = BULLET.match(line)
        personal_heading = re.match(r"^personal projects\b", line, re.IGNORECASE)

        if in_non_project_section:
            if personal_heading and not top_level:
                in_non_project_section = False
            elif numbered or (
                top_level
                and not top_level.group(1).lower().startswith("personal projects")
            ):
                in_non_project_section = False
            elif bullet and not bullet.group(1).strip():
                in_non_project_section = False
            else:
                continue

        if personal_heading and not top_level:
            finish()
            in_personal_section = True
            stack_match = re.search(r"\[([^\]]+)\]", line)
            personal_stack = (
                [clean(item) for item in re.split(r"[,/]", stack_match.group(1))]
                if stack_match
                else []
            )
            continue

        if top_level and in_personal_section and current:
            heading = clean(top_level.group(1))
            is_work_project = re.search(
                r"\[[^\]]*(?:Ltd|Limited|Infosys|TCS)\b",
                heading,
                re.IGNORECASE,
            )
            if not is_work_project:
                append_description(current, heading)
                continue
            in_personal_section = False

        if top_level:
            finish()
            heading = clean(top_level.group(1))
            if heading.lower().startswith("personal projects"):
                in_personal_section = True
                personal_stack = [
                    clean(item)
                    for item in re.split(r"[,/]", re.search(r"\[([^\]]+)\]", heading).group(1))
                ] if re.search(r"\[([^\]]+)\]", heading) else []
                continue

            title = re.split(r"\s*\[|—|–", heading, maxsplit=1)[0].strip()
            title = re.sub(r"[•·○◦]+$", "", clean(title)).strip()
            bracket_values = re.findall(r"\[([^\]]+)\]", heading)
            period = next(
                (clean(value) for value in bracket_values if DATE_RANGE.search(value)),
                "",
            )
            company = next(
                (
                    clean(value)
                    for value in bracket_values
                    if value != period and re.search(r"\b(?:Ltd|Limited|Infosys|TCS)\b", value, re.I)
                ),
                "",
            )
            url_match = RESUME_URL.search(heading)
            current = {
                "name": title,
                "company": company,
                "period": period,
                "link": url_match.group(0).rstrip(".,") if url_match else "",
                "stack": [],
                "description": "",
                "achievements": [],
            }
            continue

        if numbered:
            finish()
            details = clean(numbered.group(1))
            url_match = RESUME_URL.search(details)
            name = details[: url_match.start()] if url_match else details
            name = re.sub(r"\s*[–—-]\s*$", "", name).strip()
            name = re.sub(r"[•·○◦]+$", "", name).strip()
            current = {
                "name": clean(name),
                "company": "",
                "period": "",
                "link": url_match.group(0).rstrip(".,") if url_match else "",
                "stack": list(personal_stack),
                "description": "",
                "achievements": [],
            }
            continue

        if current and bullet:
            text = clean(bullet.group(1))
            if text:
                current["achievements"].append(text)
            else:
                awaiting_bullet_text = True
            continue

        if current and line:
            date_match = DATE_RANGE.search(line)
            if not current["achievements"] and date_match and line.startswith("["):
                current["period"] = clean(line.strip("[]"))
                continue
            if awaiting_bullet_text:
                current["achievements"].append(line)
                awaiting_bullet_text = False
            else:
                append_description(current, line)

    finish()
    return projects


def project_key(name):
    return re.sub(r"[^a-z0-9]", "", clean(name).lower())


def merge_projects(parsed, existing, prefer_parsed_description=False):
    existing_by_key = {project_key(item["name"]): item for item in existing}
    merged = []

    for project in parsed:
        previous = existing_by_key.get(project_key(project["name"]), {})
        achievements = project["achievements"]
        parsed_description = achievements[0] if achievements else ""
        description = (
            (parsed_description or previous.get("description", ""))
            if prefer_parsed_description
            else (previous.get("description") or parsed_description)
        )
        merged.append(
            {
                "name": project["name"],
                **({"company": project["company"] or previous["company"]} if project["company"] or previous.get("company") else {}),
                **({"period": project["period"] or previous["period"]} if project["period"] or previous.get("period") else {}),
                **({"link": project["link"] or previous["link"]} if project["link"] or previous.get("link") else {}),
                "stack": project["stack"] or previous.get("stack", []),
                "description": description,
                "achievements": achievements or previous.get("achievements", []),
            }
        )

    return merged


def main():
    if not RESUME_PATH.is_file():
        raise FileNotFoundError(f"Resume PDF not found: {RESUME_PATH}")
    if not PROFILE_PATH.is_file():
        raise FileNotFoundError(f"Portfolio profile JSON not found: {PROFILE_PATH}")

    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    parsed = parse_project_section(extract_project_section(RESUME_PATH))
    if not parsed:
        raise ValueError("No projects were found in the resume PROJECTS section.")

    profile["projects"] = merge_projects(parsed, profile.get("projects", []))
    PROFILE_PATH.write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Generated {len(parsed)} portfolio projects from {RESUME_PATH.name}.")
    for project in parsed:
        print(f"- {project['name']}")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"Resume project sync failed: {error}", file=sys.stderr)
        sys.exit(1)

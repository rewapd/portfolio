#!/usr/bin/env python3
import hashlib
import json
import os
import re
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

import fitz
import requests
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

from .sync_resume_projects import merge_projects, parse_project_section


ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATH = ROOT / "client/public/profile.json"
RESUME_PATH = ROOT / "client/public/Rewa-Prasad-Resume.pdf"
SYNC_STATE_PATH = ROOT / "scripts/.google-doc-sync-state.json"
SYNC_PARSER_VERSION = 10
SCOPES = [
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]
INVISIBLE = re.compile(r"[\u200b-\u200f\ufeff]")
SECTION_ALIASES = {
    "projects": {"PROJECTS", "PROJECTS & EXPERIENCE", "PROJECT EXPERIENCE"},
    "experience": {
        "EXPERIENCE",
        "WORK EXPERIENCE",
        "PROFESSIONAL EXPERIENCE",
        "WORK HISTORY",
    },
    "skills": {
        "SKILLS",
        "SKILL",
        "TECHNICAL SKILLS",
        "TECHNOLOGY SKILLS",
        "SKILL SET",
    },
    "certifications": {"CERTIFICATION", "CERTIFICATIONS"},
    "awards": {"AWARD", "AWARDS", "ACHIEVEMENTS"},
    "languages": {"LANGUAGE", "LANGUAGES"},
    "education": {"EDUCATION", "ACADEMIC QUALIFICATIONS"},
    "summary": {
        "SUMMARY",
        "PROFILE",
        "PROFILE SUMMARY",
        "PROFESSIONAL SUMMARY",
        "CAREER OBJECTIVE",
        "OBJECTIVE",
    },
}
SECTION_PREFIXES = sorted(
    ((alias, section) for section, aliases in SECTION_ALIASES.items() for alias in aliases),
    key=lambda entry: len(entry[0]),
    reverse=True,
)
SKILL_GROUPS = {
    "frontend": "frontend",
    "front end": "frontend",
    "backend": "backend",
    "back end": "backend",
    "database": "database",
    "databases": "database",
    "tools": "tools",
    "tool": "tools",
    "rpa": "rpa",
    "automation": "rpa",
}
DATE_RANGE = re.compile(
    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*"
    r"\s+\d{4}\s*[-–]\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
    r"[a-z]*\s+)?(?:\d{4}|Present)\b",
    re.IGNORECASE,
)
EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3,5}\)?[-.\s]?)?\d{6,10}(?!\d)")
LINKEDIN = re.compile(r"https?://(?:www\.)?linkedin\.com/[^\s)]+", re.IGNORECASE)
SECTION_HEADING_PATTERN = re.compile(
    r"(?<!\w)("
    + "|".join(re.escape(alias) for alias, _ in SECTION_PREFIXES)
    + r")(?=$|[\s:|])",
    re.IGNORECASE,
)


def flatten_document_content(content):
    lines = []
    for element in content:
        paragraph = element.get("paragraph")
        if paragraph:
            text = "".join(
                run.get("textRun", {}).get("content", "")
                for run in paragraph.get("elements", [])
            )
            bullet = paragraph.get("bullet")
            if bullet and text.strip():
                level = bullet.get("nestingLevel", 0)
                marker = "● " if level == 0 else "○ "
                text = marker + text.lstrip()
            lines.extend(text.splitlines())
            continue

        table = element.get("table")
        if table:
            for row in table.get("tableRows", []):
                for cell in row.get("tableCells", []):
                    lines.extend(flatten_document_content(cell.get("content", [])))

        table_of_contents = element.get("tableOfContents")
        if table_of_contents:
            lines.extend(
                flatten_document_content(table_of_contents.get("content", []))
            )

    return [clean_line(line) for line in lines if clean_line(line)]


def flatten_document_regions(content):
    regions = []
    current = []
    for element in content:
        paragraph = element.get("paragraph")
        if paragraph:
            text = "".join(
                run.get("textRun", {}).get("content", "")
                for run in paragraph.get("elements", [])
            )
            bullet = paragraph.get("bullet")
            if bullet and text.strip():
                level = bullet.get("nestingLevel", 0)
                marker = "● " if level == 0 else "○ "
                text = marker + text.lstrip()
            current.extend(clean_line(line) for line in text.splitlines() if clean_line(line))
            continue

        nested_content = None
        table = element.get("table")
        if table:
            nested_content = [
                cell.get("content", [])
                for row in table.get("tableRows", [])
                for cell in row.get("tableCells", [])
            ]
        table_of_contents = element.get("tableOfContents")
        if table_of_contents:
            nested_content = [table_of_contents.get("content", [])]

        if nested_content is not None:
            if current:
                regions.append(current)
                current = []
            for child_content in nested_content:
                regions.extend(flatten_document_regions(child_content))

    if current:
        regions.append(current)
    return regions


def clean_line(line):
    return re.sub(r"\s+", " ", INVISIBLE.sub("", line)).strip()


def document_change_token(document):
    revision_id = document.get("revisionId")
    if revision_id:
        return f"revision:{revision_id}"
    serialized = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return f"sha256:{hashlib.sha256(serialized).hexdigest()}"


def section_heading(line):
    candidate = clean_line(line).strip(" :|").upper()
    for alias, section in SECTION_PREFIXES:
        if candidate == alias:
            return section, ""
        if candidate.startswith(f"{alias} ") or candidate.startswith(f"{alias}:"):
            return section, candidate[len(alias) :].strip(" :|")
    return None, ""


def split_sections(lines):
    sections = {}
    current = None
    for line in lines:
        matches = []
        for match in SECTION_HEADING_PATTERN.finditer(line):
            prefix = line[: match.start()]
            heading_at_start = re.fullmatch(r"[\s●•○◦o:|]*", prefix) is not None
            heading_is_uppercase = match.group(0).isupper()
            if not heading_at_start and not heading_is_uppercase:
                continue
            if (
                match.group(1).upper() == "PROJECTS"
                and prefix.rstrip().lower().endswith("personal")
            ):
                continue
            matches.append(match)

        if not matches:
            if current and clean_line(line):
                sections[current].append(clean_line(line))
            continue

        cursor = 0
        for match in matches:
            before = clean_line(line[cursor : match.start()])
            if before and current:
                sections[current].append(before)
            alias = match.group(1).upper()
            current = next(
                section
                for known_alias, section in SECTION_PREFIXES
                if known_alias == alias
            )
            sections.setdefault(current, [])
            cursor = match.end()
        remainder = clean_line(line[cursor:])
        if remainder:
            sections[current].append(remainder)
    return sections


def document_sections(document):
    sections = {}
    content = document.get("body", {}).get("content", [])
    for region in flatten_document_regions(content):
        for section, lines in split_sections(region).items():
            sections.setdefault(section, []).extend(lines)
    return sections


def content_lines(lines):
    return [
        clean_line(re.sub(r"^[●•○◦o]\s*", "", line))
        for line in lines
        if clean_line(line)
    ]


def extract_projects(document):
    project_lines = document_sections(document).get("projects", [])
    if not project_lines:
        raise ValueError("Could not find a PROJECTS heading in the Google Doc.")

    projects = parse_project_section(project_lines)
    if not projects:
        raise ValueError("No projects were found below the Google Doc PROJECTS heading.")
    return projects


def extract_projects_from_pdf(pdf_data):
    pdf = fitz.open(stream=pdf_data, filetype="pdf")
    try:
        lines = [
            clean_line(line)
            for page in pdf
            for line in page.get_text("text").splitlines()
            if clean_line(line)
        ]
    finally:
        pdf.close()

    start = next(
        (index for index, line in enumerate(lines) if line.upper() in {
            "PROJECTS",
            "PROJECTS & EXPERIENCE",
            "PROJECT EXPERIENCE",
        }),
        None,
    )
    if start is None:
        raise ValueError("Could not find the PROJECTS heading in the exported PDF.")

    projects = parse_project_section(lines[start + 1 :])
    if not projects:
        raise ValueError("No projects were found in the exported PDF PROJECTS section.")
    return projects


def split_values(lines):
    values = []
    for line in content_lines(lines):
        values.extend(
            clean_line(value).strip(" ,;")
            for value in re.split(r"\s*[;|]\s*", line)
            if clean_line(value).strip(" ,;")
        )
    return values


def extract_certifications(lines):
    certification_start = re.compile(
        r"(?=\b(?:Udemy Certified|Microsoft(?: Azure| Certified)|Infosys Certified)\b)",
        re.IGNORECASE,
    )
    certifications = []
    for value in split_values(lines):
        certifications.extend(
            item.strip(" ,;")
            for item in certification_start.split(value)
            if item.strip(" ,;")
        )
    return list(dict.fromkeys(certifications))


def extract_awards(lines):
    awards = []
    current = None
    description_start = re.compile(
        r"^(?:for\b|secured\b|recognized\b|in recognition\b|awarded\b|"
        r"received\b|won\b|selected\b|contributed\b)",
        re.IGNORECASE,
    )
    description_continuation = re.compile(
        r"^(?:and|or|within|with|through|to|by|as|at|on|from|of|the)\b",
        re.IGNORECASE,
    )

    def start_award(title):
        return {"title": title, "description": ""}

    def finish():
        if current and current["title"]:
            awards.append(current)

    for line in lines:
        value = clean_line(line)
        if not value:
            continue

        bullet = re.match(r"^([●•○◦o])\s*(.*)$", value)
        if bullet:
            marker, value = bullet.groups()
            if marker in {"●", "•"}:
                finish()
                current = start_award(value)
            elif current:
                current["description"] = clean_line(
                    f'{current["description"]} {value}'
                )
            elif value:
                current = start_award(value)
            continue

        if current is None:
            current = start_award(value)
        elif current["description"] and (
            re.search(r"\b(?:award|tournament|medal|recognition|prize|champion)\b", value, re.I)
            or (
                not description_start.match(value)
                and not description_continuation.match(value)
                and not value[0].islower()
            )
        ):
            finish()
            current = start_award(value)
        elif not current["description"]:
            current["description"] = value
        else:
            current["description"] = clean_line(
                f'{current["description"]} {value}'
            )

    finish()
    return awards


def extract_skills(lines):
    groups = {}
    aliases = {
        "frontend": "frontend",
        "front end": "frontend",
        "backend": "backend",
        "back end": "backend",
        "database": "database",
        "databases": "database",
        "tools": "tools",
        "tool": "tools",
        "rpa": "rpa",
        "automation": "rpa",
    }
    label_pattern = re.compile(
        r"(?i)(?<![\w])Front\s*end|Back\s*end|Databases?|Tools?|Automation(?![\w])"
    )
    active_group = None

    def add_values(group, value):
        values = re.split(r"\s*[,;/]\s*", clean_line(value).strip(" :-"))
        groups.setdefault(group, []).extend(
            clean_line(item).strip(" .")
            for item in values
            if clean_line(item).strip(" .")
        )

    for line in lines:
        value = clean_line(re.sub(r"^[●•○◦o]\s*", "", line))
        matches = list(label_pattern.finditer(value))
        if len(value.split()) == 1 and value.lower().rstrip(":") in aliases:
            active_group = aliases[value.lower().rstrip(":")]
            groups.setdefault(active_group, [])
            continue
        if not matches:
            if active_group:
                add_values(active_group, value)
            elif value:
                groups.setdefault("general", []).extend(
                    item.strip(" .")
                    for item in re.split(r"\s*[,;/]\s*", value)
                    if item.strip(" .")
                )
            continue

        prefix = value[: matches[0].start()].strip(" :-")
        if prefix and active_group:
            add_values(active_group, prefix)
        for index, match in enumerate(matches):
            alias = re.sub(r"\s+", " ", match.group(0).lower())
            group = aliases.get(alias)
            if not group:
                continue
            end = matches[index + 1].start() if index + 1 < len(matches) else len(value)
            add_values(group, value[match.end() : end])
            active_group = group

    skills = {
        group: list(dict.fromkeys(items))
        for group, items in groups.items()
        if items
    }
    if set(skills) <= {"general"}:
        values = split_values(lines)
        if values:
            skills = {"general": values}
    return skills


def extract_education(lines):
    education = []
    current = None
    degree_pattern = re.compile(
        r"\b(?:B\.?Tech|B\.?E\.?|M\.?Tech|M\.?S\.?|B\.?Sc|M\.?Sc|"
        r"Ph\.?D|Higher Secondary|Senior Secondary|Bachelor|Master|Diploma|Senior)\b",
        re.IGNORECASE,
    )

    def finish():
        if current and current.get("school"):
            education.append(
                {key: value for key, value in current.items() if value}
            )

    for line in content_lines(lines):
        parts = [clean_line(part) for part in re.split(r"\s*[|;]\s*", line) if part.strip()]
        for part in parts:
            if not part:
                continue
            date_match = DATE_RANGE.search(part)
            gpa_match = re.search(r"\bGPA\s*:?\s*[\d.]+(?:\s*/\s*[\d.]+)?", part, re.I)
            degree_match = degree_pattern.search(part)
            is_school = re.search(
                r"\b(?:university|institute|college|school|academy)\b", part, re.I
            )
            if is_school and (current is None or current.get("school")):
                finish()
                school = part
                degree = ""
                school_with_degree = re.split(r"\s*[—–-]\s*", part, maxsplit=1)
                if len(school_with_degree) == 2:
                    school_part, degree_hint = school_with_degree
                    school = school_part.strip(" ,:-")
                    degree_hint = degree_hint.strip(" ,:-")
                    if degree_hint:
                        degree = degree_hint
                    if re.search(r"\bSenior\s+Secondary\b", school_part, re.I):
                        degree = "Senior Secondary"
                    elif re.search(r"\bHigher\s+Secondary\b", school_part, re.I):
                        degree = "Higher Secondary"
                elif degree_match:
                    degree = degree_match.group(0)
                    school = part[: degree_match.start()].rstrip(" —–-,:")
                    trailing = part[degree_match.end() :].strip(" ,:-")
                    if trailing:
                        degree = f"{degree} {trailing}"
                elif re.search(r"[—–-]\s*Senior$", part, re.I):
                    school = re.sub(r"[—–-]\s*Senior$", "", part, flags=re.I).strip()
                    degree = "Senior"
                current = {"school": school}
                if degree:
                    current["degree"] = degree
                continue
            if current is None:
                current = {}
            if current.get("degree") in {"Senior", "Senior Secondary"} and re.fullmatch(
                r"Secondary", part, re.I
            ):
                current["degree"] = "Senior Secondary"
                continue
            if date_match:
                current["period"] = date_match.group(0)
            if gpa_match:
                current["gpa"] = gpa_match.group(0)
            if degree_match:
                current["degree"] = degree_match.group(0)
                field = part[degree_match.end() :].strip(" ,:-")
                if field and not date_match and not gpa_match:
                    current["field"] = field
            elif is_school:
                current["school"] = part
            elif current.get("school") and not date_match and not gpa_match:
                current.setdefault("field", part)
    finish()
    return education


def extract_experiences(lines, projects):
    experiences = []
    current = None
    company_pattern = re.compile(
        r"\b(?:Tata Consultancy Services|Infosys(?:\s+Ltd\.?)?|"
        r"[A-Z][A-Za-z& ]+\s+(?:Ltd|Limited|Inc|Corporation))\b",
        re.IGNORECASE,
    )

    def finish():
        if current and current.get("company"):
            current["highlights"] = list(dict.fromkeys(current["highlights"]))
            experiences.append(current.copy())

    for line in lines:
        value = clean_line(re.sub(r"^[●•○◦o]\s*", "", line))
        if not value:
            continue
        company_match = company_pattern.search(value)
        if company_match and (
            current is None
            or current.get("company")
            or DATE_RANGE.search(value)
        ):
            finish()
            current = {
                "company": company_match.group(0),
                "location": "",
                "role": "",
                "duration": "",
                "type": "",
                "highlights": [],
            }
            remainder = value[company_match.end() :].strip(" -|,")
            if "—" in remainder or "–" in remainder:
                location, role = re.split(r"\s*[—–]\s*", remainder, maxsplit=1)
                current["location"] = location.strip(" ,")
                current["role"] = role.strip(" ,")
                remainder = ""
            date_match = DATE_RANGE.search(remainder)
            if date_match:
                current["duration"] = date_match.group(0)
            role = (
                re.sub(r"\b" + re.escape(date_match.group(0)) + r"\b", "", remainder)
                .strip(" -–—|,")
                if date_match
                else remainder.strip(" -–—|,")
            )
            if role:
                current["role"] = role
            continue
        if current is None:
            continue
        date_match = DATE_RANGE.search(value)
        if date_match and not current["duration"]:
            current["duration"] = date_match.group(0)
            role = clean_line(value.replace(date_match.group(0), "").strip(" -|,"))
            if role and not current["role"]:
                current["role"] = role
        elif re.match(r"^(?:Location|Based in)\s*:", value, re.I):
            current["location"] = value.split(":", 1)[1].strip()
        elif re.fullmatch(
            r"(?:Software Developer|RPA Developer|Java Developer|"
            r"Windchill Developer|Technical Lead)",
            value,
            re.I,
        ):
            current["type"] = value
        elif value:
            current["highlights"].append(value)
    finish()

    if experiences:
        return experiences

    # Some resumes describe employment only as company-tagged project entries.
    for project in projects:
        company = project.get("company")
        if not company:
            continue
        matched = next(
            (item for item in experiences if item["company"].lower() == company.lower()),
            None,
        )
        if not matched:
            matched = {
                "company": company,
                "location": "",
                "role": project["name"],
                "duration": project.get("period", ""),
                "type": "",
                "highlights": [],
            }
            experiences.append(matched)
        matched["highlights"].extend(project.get("achievements", []))
    return experiences


def extract_profile(document, existing, projects):
    lines = flatten_document_content(document.get("body", {}).get("content", []))
    sections = document_sections(document)
    result = dict(existing)

    header = []
    for line in lines:
        if section_heading(line)[0]:
            break
        if clean_line(line):
            header.append(clean_line(line))

    labeled = {}
    for line in lines:
        for label, value in re.findall(
            r"(?i)\b(Name|Role|Title|Headline|Summary|Location|Address|Phone|Mobile|Email|LinkedIn)\s*:\s*(.*?)(?=\s+(?:Name|Role|Title|Headline|Summary|Location|Address|Phone|Mobile|Email|LinkedIn)\s*:|$)",
            line,
        ):
            labeled[label.lower()] = clean_line(value)

    if labeled.get("name"):
        result["name"] = labeled["name"]
    elif header:
        candidate = header[0]
        if not re.search(r"[@\d]|https?://", candidate) and len(candidate.split()) <= 5:
            result["name"] = candidate
    if labeled.get("role") or labeled.get("title"):
        result["role"] = labeled.get("role") or labeled["title"]
    elif len(header) > 1 and re.search(
        r"\b(?:developer|engineer|consultant|analyst|manager)\b", header[1], re.I
    ):
        result["role"] = header[1]
    if labeled.get("headline"):
        result["headline"] = labeled["headline"]
    if labeled.get("summary"):
        result["summary"] = labeled["summary"]
        if not labeled.get("headline"):
            result["headline"] = result["summary"].split(". ", 1)[0].strip()
    elif sections.get("summary"):
        result["summary"] = " ".join(content_lines(sections["summary"]))
        if not labeled.get("headline"):
            result["headline"] = result["summary"].split(". ", 1)[0].strip()
    else:
        unlabeled_header = [
            line
            for line in header
            if not re.match(
                r"(?i)^(?:name|role|title|headline|summary|location|address|"
                r"phone|mobile|email|linkedin)\s*:",
                line,
            )
            and not EMAIL.search(line)
            and not PHONE.fullmatch(line)
            and not LINKEDIN.search(line)
            and not re.search(
                r"\b(?:developer|engineer|consultant|analyst|manager)\b",
                line,
                re.I,
            )
        ]
        descriptive_header = [
            line for line in unlabeled_header if len(line.split()) >= 8
        ]
        if descriptive_header and not labeled.get("headline"):
            result["headline"] = descriptive_header[0]
        if descriptive_header:
            result["summary"] = " ".join(descriptive_header)

    contact = dict(existing.get("contact", {}))
    all_text = "\n".join(lines)
    email_match = EMAIL.search(all_text)
    phone_match = PHONE.search(
        labeled.get("phone", "") or labeled.get("mobile", "") or all_text
    )
    linkedin_match = LINKEDIN.search(all_text)
    if email_match:
        contact["email"] = email_match.group(0)
    if phone_match:
        contact["phone"] = phone_match.group(0).strip()
    if linkedin_match:
        contact["linkedin"] = linkedin_match.group(0).rstrip(".,")
    if labeled.get("location") or labeled.get("address"):
        contact["location"] = labeled.get("location") or labeled["address"]
    else:
        address = next(
            (
                line
                for line in header
                if re.search(r"\b\d{6}\b", line)
                and re.search(r"\b(?:Pune|Mumbai|Delhi|Bengaluru|Hyderabad)\b", line, re.I)
            ),
            None,
        )
        if address:
            contact["location"] = address
    result["contact"] = contact

    if sections.get("skills"):
        skills = extract_skills(sections["skills"])
        if skills:
            result["skills"] = skills
    if sections.get("certifications"):
        certifications = extract_certifications(sections["certifications"])
        if certifications:
            result["certifications"] = certifications
    if sections.get("awards"):
        awards = extract_awards(sections["awards"])
        if awards:
            result["awards"] = awards
    if sections.get("languages"):
        languages = split_values(sections["languages"])
        if len(languages) == 1:
            languages = [clean_line(value) for value in languages[0].split(",") if value.strip()]
        if languages:
            result["languages"] = languages
    if sections.get("education"):
        education = extract_education(sections["education"])
        if education:
            result["education"] = education
    if sections.get("experience"):
        experiences = extract_experiences(sections["experience"], projects)
        if experiences:
            result["experiences"] = experiences
    elif projects:
        result["experiences"] = extract_experiences([], projects)

    result["projects"] = merge_projects(
        projects,
        existing.get("projects", []),
        prefer_parsed_description=True,
    )
    result["metrics"] = update_metrics(result, existing.get("metrics", []))
    return result


def update_metrics(profile, existing_metrics):
    values = {item["label"]: item["value"] for item in existing_metrics}
    certifications = profile.get("certifications", [])
    if certifications:
        values["Certifications"] = str(len(certifications))
    stack = []
    for skills in profile.get("skills", {}).values():
        for skill in skills:
            if skill not in stack:
                stack.append(skill)
    if stack:
        preferred_stack = ["Windchill", "Java", "Javascript", "React.js"]
        core_stack = [
            preferred
            for preferred in preferred_stack
            if any(skill.lower() == preferred.lower() for skill in stack)
        ]
        core_stack.extend(
            skill
            for skill in stack
            if skill.lower() not in {item.lower() for item in core_stack}
        )
        core_stack = core_stack[:4]
        values["Core Stack"] = ", ".join(core_stack)
    years = re.search(r"\b(\d+\+?\s+years?)\b", profile.get("summary", ""), re.I)
    if years:
        values["Experience"] = years.group(1)
    if profile.get("role"):
        values["Focus"] = profile["role"]
    return [
        {"label": label, "value": value}
        for label, value in values.items()
    ]


def make_session(service_account_json):
    try:
        info = json.loads(service_account_json)
        credentials = service_account.Credentials.from_service_account_info(
            info, scopes=SCOPES
        )
    except (json.JSONDecodeError, KeyError, ValueError) as error:
        raise ValueError(
            "GOOGLE_SERVICE_ACCOUNT_JSON must contain valid Google service account JSON."
        ) from error

    return AuthorizedSession(credentials)


def get_response(session, url, kind):
    try:
        response = session.get(url, timeout=45)
    except requests.RequestException as error:
        raise RuntimeError(f"Could not connect to the Google {kind} API.") from error

    if not response.ok:
        if response.status_code in (401, 403):
            raise RuntimeError(
                f"Google {kind} API denied access. Enable the Docs and Drive APIs, "
                "and share the Google Doc with the service account email as a Viewer."
            )
        try:
            response.raise_for_status()
        except requests.RequestException as error:
            raise RuntimeError(
                f"Google {kind} API request failed with HTTP {response.status_code}."
            ) from error
    return response


def fetch_google_doc(session, document_id):
    encoded_id = quote(document_id, safe="")
    response = get_response(
        session,
        f"https://docs.googleapis.com/v1/documents/{encoded_id}",
        "Docs",
    )
    return response.json()


def fetch_google_doc_pdf(session, document_id):
    encoded_id = quote(document_id, safe="")
    response = get_response(
        session,
        f"https://www.googleapis.com/drive/v3/files/{encoded_id}/export"
        "?mimeType=application%2Fpdf",
        "Drive",
    )
    pdf_data = response.content
    if not pdf_data.startswith(b"%PDF"):
        raise ValueError("Google Drive export did not return a valid PDF.")
    return pdf_data


def write_atomically(path, contents):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as temporary:
            temporary.write(contents)
            temporary_path = Path(temporary.name)
        temporary_path.replace(path)
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def main():
    document_id = os.environ.get("GOOGLE_DOC_ID", "").strip()
    service_account_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if not document_id:
        raise ValueError("Set the GOOGLE_DOC_ID GitHub Actions variable.")
    if not service_account_json:
        raise ValueError("Set the GOOGLE_SERVICE_ACCOUNT_JSON GitHub Actions secret.")
    if not PROFILE_PATH.is_file():
        raise FileNotFoundError(f"Portfolio profile JSON not found: {PROFILE_PATH}")

    session = make_session(service_account_json)
    document = fetch_google_doc(session, document_id)
    change_token = document_change_token(document)
    if SYNC_STATE_PATH.is_file():
        previous_state = json.loads(SYNC_STATE_PATH.read_text(encoding="utf-8"))
        if (
            previous_state.get("changeToken") == change_token
            and previous_state.get("parserVersion") == SYNC_PARSER_VERSION
            and PROFILE_PATH.is_file()
            and RESUME_PATH.is_file()
        ):
            print("Google Doc revision is unchanged; the portfolio is already current.")
            return

    pdf_data = fetch_google_doc_pdf(session, document_id)
    projects = extract_projects_from_pdf(pdf_data)

    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    profile = extract_profile(document, profile, projects)
    profile_data = (
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")

    write_atomically(RESUME_PATH, pdf_data)
    write_atomically(PROFILE_PATH, profile_data)
    state_data = (
        json.dumps(
            {"changeToken": change_token, "parserVersion": SYNC_PARSER_VERSION}
        )
        + "\n"
    ).encode("utf-8")
    write_atomically(SYNC_STATE_PATH, state_data)
    print(
        f"Synced profile sections and {len(projects)} projects, "
        "plus the latest PDF from Google Docs."
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Google Doc sync failed: {error}", file=sys.stderr)
        sys.exit(1)

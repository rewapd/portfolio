#!/usr/bin/env python3
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
SCOPES = [
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]
PROJECTS_START = {"PROJECTS", "PROJECTS & EXPERIENCE", "PROJECT EXPERIENCE"}
INVISIBLE = re.compile(r"[\u200b-\u200f\ufeff]")


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


def clean_line(line):
    return re.sub(r"\s+", " ", INVISIBLE.sub("", line)).strip()


def extract_projects(document):
    lines = flatten_document_content(document.get("body", {}).get("content", []))
    start = next(
        (index for index, line in enumerate(lines) if line.upper() in PROJECTS_START),
        None,
    )
    if start is None:
        raise ValueError("Could not find a PROJECTS heading in the Google Doc.")

    projects = parse_project_section(lines[start + 1 :])
    if not projects:
        raise ValueError("No projects were found below the Google Doc PROJECTS heading.")
    return projects


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
    revision_id = document.get("revisionId")
    if not revision_id:
        raise ValueError("Google Docs API response did not include a revision ID.")
    if SYNC_STATE_PATH.is_file():
        previous_state = json.loads(SYNC_STATE_PATH.read_text(encoding="utf-8"))
        if (
            previous_state.get("revisionId") == revision_id
            and PROFILE_PATH.is_file()
            and RESUME_PATH.is_file()
        ):
            print("Google Doc revision is unchanged; the portfolio is already current.")
            return

    projects = extract_projects(document)
    pdf_data = fetch_google_doc_pdf(session, document_id)

    profile = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    profile["projects"] = merge_projects(projects, profile.get("projects", []))
    profile_data = (json.dumps(profile, ensure_ascii=False, indent=2) + "\n").encode(
        "utf-8"
    )

    write_atomically(RESUME_PATH, pdf_data)
    write_atomically(PROFILE_PATH, profile_data)
    state_data = (json.dumps({"revisionId": revision_id}) + "\n").encode("utf-8")
    write_atomically(SYNC_STATE_PATH, state_data)
    print(f"Synced {len(projects)} projects and the latest PDF from Google Docs.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Google Doc sync failed: {error}", file=sys.stderr)
        sys.exit(1)

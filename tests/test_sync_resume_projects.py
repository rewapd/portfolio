import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts import sync_google_doc
from scripts.sync_resume_projects import merge_projects, parse_project_section
from scripts.sync_google_doc import extract_projects


class ResumeProjectParsingTests(unittest.TestCase):
    def test_extracts_projects_from_google_docs_document_structure(self):
        document = {
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [{"textRun": {"content": "PROJECTS\n"}}]
                        }
                    },
                    {
                        "paragraph": {
                            "bullet": {"nestingLevel": 0},
                            "elements": [
                                {
                                    "textRun": {
                                        "content": "Platform Build [Example Ltd] — Manufacturing\n"
                                    }
                                }
                            ],
                        }
                    },
                    {
                        "paragraph": {
                            "bullet": {"nestingLevel": 1},
                            "elements": [
                                {
                                    "textRun": {
                                        "content": "Built a data validation workflow.\n"
                                    }
                                }
                            ],
                        }
                    },
                    {
                        "paragraph": {
                            "elements": [
                                {"textRun": {"content": "Personal Projects\n"}}
                            ]
                        }
                    },
                    {
                        "paragraph": {
                            "elements": [
                                {
                                    "textRun": {
                                        "content": "#1: Recipe Box — https://example.com\n"
                                    }
                                }
                            ]
                        }
                    },
                    {
                        "paragraph": {
                            "bullet": {"nestingLevel": 0},
                            "elements": [
                                {
                                    "textRun": {
                                        "content": "Built a recipe finder.\n"
                                    }
                                }
                            ],
                        }
                    },
                ]
            }
        }

        projects = extract_projects(document)

        self.assertEqual(
            [project["name"] for project in projects],
            ["Platform Build", "Recipe Box"],
        )
        self.assertEqual(projects[0]["company"], "Example Ltd")
        self.assertEqual(
            projects[0]["achievements"], ["Built a data validation workflow."]
        )
        self.assertEqual(projects[1]["link"], "https://example.com")

    def test_parses_work_and_numbered_personal_projects(self):
        projects = parse_project_section(
            [
                "● Cloud Platform [Example Ltd] — Banking [Jan 2024-Present]",
                "○",
                "Designed a new data workflow.",
                "○",
                "Integrated service APIs.",
                "● Personal Projects [JavaScript, React.js]",
                "#1 : Recipe Box – https://example.com/recipes/",
                "○",
                "Built a searchable recipe application.",
                "#2 : Movie Shelf – https://example.com/movies/",
                "○",
                "Added personal ratings.",
            ]
        )

        self.assertEqual(
            [project["name"] for project in projects],
            ["Cloud Platform", "Recipe Box", "Movie Shelf"],
        )
        self.assertEqual(projects[0]["company"], "Example Ltd")
        self.assertEqual(projects[0]["period"], "Jan 2024-Present")
        self.assertEqual(
            projects[0]["achievements"],
            ["Designed a new data workflow.", "Integrated service APIs."],
        )
        self.assertEqual(projects[1]["link"], "https://example.com/recipes/")
        self.assertEqual(projects[1]["stack"], ["JavaScript", "React.js"])
        self.assertEqual(projects[2]["link"], "https://example.com/movies/")

    def test_refreshes_resume_content_and_preserves_curated_project_link(self):
        merged = merge_projects(
            [
                {
                    "name": "Movie Shelf",
                    "company": "",
                    "period": "",
                    "link": "",
                    "stack": ["JavaScript"],
                    "description": "",
                    "achievements": ["Added filtering."],
                },
                {
                    "name": "New Project",
                    "company": "",
                    "period": "",
                    "link": "",
                    "stack": [],
                    "description": "",
                    "achievements": ["Built a new app."],
                },
            ],
            [
                {
                    "name": "Movie Shelf",
                    "link": "https://example.com/movies/",
                    "stack": ["React.js"],
                    "description": "Movie discovery.",
                    "achievements": ["Old resume bullet."],
                }
            ],
        )

        self.assertEqual(merged[0]["link"], "https://example.com/movies/")
        self.assertEqual(merged[0]["description"], "Movie discovery.")
        self.assertEqual(merged[0]["achievements"], ["Added filtering."])
        self.assertEqual(merged[1]["description"], "Built a new app.")

    def test_skips_export_when_google_doc_revision_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = root / "profile.json"
            resume_path = root / "resume.pdf"
            state_path = root / "sync-state.json"
            profile_path.write_text('{"projects": []}\n', encoding="utf-8")
            resume_path.write_bytes(b"%PDF-existing")
            state_path.write_text(
                json.dumps({"revisionId": "revision-1"}), encoding="utf-8"
            )

            with patch.dict(
                os.environ,
                {
                    "GOOGLE_DOC_ID": "document-id",
                    "GOOGLE_SERVICE_ACCOUNT_JSON": "service-account-json",
                },
            ), patch.object(
                sync_google_doc, "PROFILE_PATH", profile_path
            ), patch.object(
                sync_google_doc, "RESUME_PATH", resume_path
            ), patch.object(
                sync_google_doc, "SYNC_STATE_PATH", state_path
            ), patch.object(
                sync_google_doc, "make_session"
            ), patch.object(
                sync_google_doc, "fetch_google_doc", return_value={"revisionId": "revision-1"}
            ), patch.object(
                sync_google_doc, "fetch_google_doc_pdf"
            ) as export_pdf:
                sync_google_doc.main()

            export_pdf.assert_not_called()
            self.assertEqual(resume_path.read_bytes(), b"%PDF-existing")


if __name__ == "__main__":
    unittest.main()

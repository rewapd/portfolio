import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import fitz

from scripts import sync_google_doc
from scripts.sync_resume_projects import merge_projects, parse_project_section
from scripts.sync_google_doc import (
    document_change_token,
    extract_awards,
    extract_certifications,
    extract_education,
    extract_profile,
    extract_projects,
    extract_projects_from_pdf,
    update_metrics,
)


class ResumeProjectParsingTests(unittest.TestCase):
    def test_extracts_work_and_personal_projects_line_by_line_from_pdf(self):
        pdf = fitz.open()
        page = pdf.new_page()
        page.insert_text(
            (36, 40),
            "\n".join(
                [
                    "PROJECTS",
                    "● Lead Engineer [Example Ltd] — Platform [Jan 2024-Present]",
                    "○",
                    "Built the platform.",
                    "● Personal Projects [JavaScript, React.js]",
                    "#1 : Movie Shelf – https://example.com/movies",
                    "○",
                    "Search movies.",
                    "○",
                    "Save ratings locally.",
                    "#2 : Recipe Book – https://example.com/recipes",
                    "○",
                    "Find recipes.",
                    "PROJECT NOTES",
                    "Done",
                ]
            ),
        )
        pdf_data = pdf.tobytes()
        pdf.close()

        projects = extract_projects_from_pdf(pdf_data)

        self.assertEqual(
            [project["name"] for project in projects],
            ["Lead Engineer", "Movie Shelf", "Recipe Book"],
        )
        self.assertEqual(projects[0]["company"], "Example Ltd")
        self.assertEqual(projects[0]["achievements"], ["Built the platform."])
        self.assertEqual(projects[1]["stack"], ["JavaScript", "React.js"])
        self.assertEqual(projects[1]["link"], "https://example.com/movies")
        self.assertEqual(
            projects[1]["achievements"],
            ["Search movies.", "Save ratings locally."],
        )

    def test_extracts_degrees_and_schools_without_course_fallback(self):
        education = extract_education(
            [
                "Haldia Institute of Technology, Haldia — B.Tech",
                "July 2011 - June 2015",
                "Instrumentation and Control Engineering",
                "GPA: 8.40/10",
                "Mother Khazani Convent School, Delhi — Higher Secondary",
                "April 2009 - March 2011",
                "Physics, Chemistry and Maths",
                "JawaharLal Nehru Memorial Senior Secondary School, Dhanbad — Senior",
                "Secondary",
                "April 2008 - March 2009",
            ]
        )

        self.assertEqual(len(education), 3)
        self.assertEqual(education[0]["degree"], "B.Tech")
        self.assertEqual(
            education[0]["school"], "Haldia Institute of Technology, Haldia"
        )
        self.assertEqual(education[1]["degree"], "Higher Secondary")
        self.assertEqual(education[2]["degree"], "Senior Secondary")
        self.assertEqual(
            education[2]["school"],
            "JawaharLal Nehru Memorial Senior Secondary School, Dhanbad",
        )
        self.assertNotIn("field", education[2])

    def test_document_change_token_uses_revision_or_content_hash(self):
        self.assertEqual(
            document_change_token({"revisionId": "rev-123", "body": {}}),
            "revision:rev-123",
        )
        first = document_change_token({"body": {"content": [{"text": "first"}]}})
        unchanged = document_change_token(
            {"body": {"content": [{"text": "first"}]}}
        )
        updated = document_change_token(
            {"body": {"content": [{"text": "updated"}]}}
        )

        self.assertTrue(first.startswith("sha256:"))
        self.assertEqual(first, unchanged)
        self.assertNotEqual(first, updated)

    def test_extracts_certifications_when_two_titles_share_a_line(self):
        certifications = extract_certifications(
            [
                "Udemy Certified- Java DS & Algo",
                "Udemy Certified- React.js",
                "Microsoft Azure Fundamentals",
                "Infosys Certified Agile Developer Infosys Certified DevOps Professional",
                "Microsoft Azure AI Fundamentals",
            ]
        )

        self.assertEqual(
            certifications,
            [
                "Udemy Certified- Java DS & Algo",
                "Udemy Certified- React.js",
                "Microsoft Azure Fundamentals",
                "Infosys Certified Agile Developer",
                "Infosys Certified DevOps Professional",
                "Microsoft Azure AI Fundamentals",
            ],
        )

    def test_groups_award_explanations_under_their_award_titles(self):
        awards = extract_awards(
            [
                "Innovation Superstar Award",
                "For outstanding contribution",
                "Insta award",
                "For quickly taking up issues and",
                "taking additional responsibilities",
                "within the team",
                "Table Tennis Tournament",
                "Secured 1st position",
            ]
        )

        self.assertEqual(
            awards,
            [
                {
                    "title": "Innovation Superstar Award",
                    "description": "For outstanding contribution",
                },
                {
                    "title": "Insta award",
                    "description": "For quickly taking up issues and taking additional responsibilities within the team",
                },
                {
                    "title": "Table Tennis Tournament",
                    "description": "Secured 1st position",
                },
            ],
        )

    def test_metrics_include_experience_and_windchill_in_core_stack(self):
        metrics = update_metrics(
            {
                "summary": "Software Developer with 10+ years of experience.",
                "role": "Software Developer",
                "skills": {
                    "frontend": ["Javascript", "React.js", "HTML"],
                    "backend": ["Java"],
                    "tools": ["Windchill"],
                },
            },
            [
                {"label": "Experience", "value": "9+ years"},
                {"label": "Core Stack", "value": "old stack"},
            ],
        )
        values = {item["label"]: item["value"] for item in metrics}

        self.assertEqual(values["Experience"], "10+ years")
        self.assertEqual(
            values["Core Stack"], "Windchill, Java, Javascript, React.js"
        )

    def test_keeps_table_columns_separate_when_extracting_projects_and_skills(self):
        def paragraph(text, bullet=False):
            return {
                "paragraph": {
                    **({"bullet": {"nestingLevel": 0}} if bullet else {}),
                    "elements": [{"textRun": {"content": text + "\n"}}],
                }
            }

        document = {
            "body": {
                "content": [
                    {
                        "table": {
                            "tableRows": [
                                {
                                    "tableCells": [
                                        {
                                            "content": [
                                                paragraph("PROJECTS"),
                                                paragraph("● Alpha [Example Ltd] — Platform"),
                                                paragraph("○ Built a platform."),
                                            ]
                                        },
                                        {
                                            "content": [
                                                paragraph("SKILLS"),
                                                paragraph("Frontend"),
                                                paragraph("JavaScript, React.js"),
                                                paragraph("Backend"),
                                                paragraph("Node.js"),
                                                paragraph("Database"),
                                                paragraph("PostgreSQL"),
                                                paragraph("Tools"),
                                                paragraph("GitHub, Docker, Kofax RPA"),
                                            ]
                                        },
                                    ]
                                }
                            ]
                        }
                    }
                ]
            }
        }

        projects = extract_projects(document)
        profile = extract_profile(
            document,
            {"projects": [], "skills": {}, "metrics": []},
            projects,
        )

        self.assertEqual([project["name"] for project in projects], ["Alpha"])
        self.assertEqual(projects[0]["achievements"], ["Built a platform."])
        self.assertEqual(
            profile["skills"],
            {
                "frontend": ["JavaScript", "React.js"],
                "backend": ["Node.js"],
                "database": ["PostgreSQL"],
                "tools": ["GitHub", "Docker", "Kofax RPA"],
            },
        )

    def test_extracts_all_supported_portfolio_sections_from_google_docs(self):
        content = [
            ("Name: Rewa Updated", False),
            ("Role: Platform Engineer", False),
            ("Email: rewa.updated@example.com", False),
            ("Phone: +91 9876543210", False),
            ("Location: Pune, India", False),
            ("LinkedIn: https://www.linkedin.com/in/rewa-updated/", False),
            ("SUMMARY", False),
            ("Platform Engineer with 8 years of experience.", False),
            ("EXPERIENCE", False),
            ("Acme Ltd, Pune — Senior Engineer", True),
            ("Jan 2020 - Present", False),
            ("Software Developer", False),
            ("Led delivery of scalable services.", True),
            ("PROJECTS", False),
            ("Project Alpha [Acme Ltd] [Jan 2024-Present]", True),
            ("Delivered a new customer platform.", False),
            ("SKILLS", False),
            ("Frontend: TypeScript, React", False),
            ("Backend: Node.js", False),
            ("Database: PostgreSQL", False),
            ("Tools: GitHub, Docker", False),
            ("CERTIFICATIONS", False),
            ("Cloud Architecture", True),
            ("AWARDS", False),
            ("Engineering Excellence", True),
            ("LANGUAGES", False),
            ("English, Hindi", False),
            ("EDUCATION", False),
            ("Example University, Pune", False),
            ("B.Tech Instrumentation", False),
            ("July 2011 - June 2015", False),
            ("GPA: 8.4/10", False),
        ]
        document = {
            "body": {
                "content": [
                    {
                        "paragraph": {
                            **({"bullet": {"nestingLevel": 0}} if bullet else {}),
                            "elements": [{"textRun": {"content": text + "\n"}}],
                        }
                    }
                    for text, bullet in content
                ]
            }
        }
        existing = {
            "name": "Old Name",
            "role": "Old Role",
            "headline": "Old headline",
            "summary": "Old summary",
            "contact": {
                "location": "Old location",
                "phone": "0000000000",
                "email": "old@example.com",
                "linkedin": "https://linkedin.com/old",
            },
            "metrics": [
                {"label": "Experience", "value": "4 years"},
                {"label": "Core Stack", "value": "Old stack"},
                {"label": "Certifications", "value": "1"},
                {"label": "Focus", "value": "Old focus"},
            ],
            "experiences": [],
            "projects": [],
            "skills": {},
            "certifications": [],
            "awards": [],
            "education": [],
            "languages": [],
        }

        projects = extract_projects(document)
        profile = extract_profile(document, existing, projects)

        self.assertEqual(profile["name"], "Rewa Updated")
        self.assertEqual(profile["role"], "Platform Engineer")
        self.assertEqual(profile["summary"], "Platform Engineer with 8 years of experience.")
        self.assertEqual(
            profile["headline"], "Platform Engineer with 8 years of experience."
        )
        self.assertEqual(profile["contact"]["email"], "rewa.updated@example.com")
        self.assertEqual(profile["contact"]["phone"], "+91 9876543210")
        self.assertEqual(profile["contact"]["location"], "Pune, India")
        self.assertEqual(
            profile["contact"]["linkedin"],
            "https://www.linkedin.com/in/rewa-updated/",
        )
        self.assertEqual(profile["skills"]["database"], ["PostgreSQL"])
        self.assertEqual(profile["certifications"], ["Cloud Architecture"])
        self.assertEqual(
            profile["awards"],
            [{"title": "Engineering Excellence", "description": ""}],
        )
        self.assertEqual(profile["languages"], ["English", "Hindi"])
        self.assertEqual(profile["education"][0]["school"], "Example University, Pune")
        self.assertEqual(profile["education"][0]["degree"], "B.Tech")
        self.assertEqual(profile["experiences"][0]["company"], "Acme Ltd")
        self.assertEqual(profile["experiences"][0]["role"], "Senior Engineer")
        self.assertEqual(profile["experiences"][0]["location"], "Pune")
        self.assertEqual(profile["experiences"][0]["type"], "Software Developer")
        self.assertEqual(
            profile["experiences"][0]["highlights"],
            ["Led delivery of scalable services."],
        )
        self.assertEqual(profile["projects"][0]["name"], "Project Alpha")
        self.assertEqual(
            profile["projects"][0]["description"],
            "Delivered a new customer platform.",
        )
        self.assertEqual(
            {item["label"]: item["value"] for item in profile["metrics"]}[
                "Certifications"
            ],
            "1",
        )

    def test_phone_extraction_ignores_linkedin_id_and_location_postcode(self):
        content = [
            "Rewa Prasad",
            "Software Developer",
            "https://www.linkedin.com/in/rewa-prasad-653397a3/",
            "Pune - 411057",
            "+91 7063470203",
            "rewa104@gmail.com",
            "PROJECTS",
            "● Project Alpha [Acme Ltd]",
            "○ Delivered a platform.",
        ]
        document = {
            "body": {
                "content": [
                    {
                        "paragraph": {
                            "elements": [{"textRun": {"content": line + "\n"}}]
                        }
                    }
                    for line in content
                ]
            }
        }
        projects = extract_projects(document)
        existing = {
            "name": "Rewa Prasad",
            "role": "Software Developer",
            "contact": {"phone": "0000000000"},
            "metrics": [],
            "projects": [],
            "skills": {},
            "certifications": [],
            "awards": [],
            "education": [],
            "languages": [],
            "experiences": [],
        }

        profile = extract_profile(document, existing, projects)

        self.assertEqual(profile["contact"]["phone"], "+91 7063470203")

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

    def test_ignores_inline_resume_sections_between_project_bullets(self):
        projects = parse_project_section(
            [
                "● Windchill Developer [Tata Consultancy Services Ltd] [Jul 2022-Mar 2026]",
                "○ Worked on OIR, lifecycle, document, product templates, Acls.",
                "SKILLS Frontend Javascript, React.js, HTML, CSS Backend Java, SpringBoot DataBase SQL Tools Windchill",
                "CERTIFICATION Udemy Certified- Java DS & Algo AWARDS Innovation Superstar Award",
                "○",
                "Developed custom user picker for global attributes.",
                "○",
                "Worked with existing utilities for creating users, groups and roles.",
                "● Robotics Process Automation [Infosys Ltd] [Jan 2019-June 2022]",
                "○ Built and maintained automation workflows.",
            ]
        )

        self.assertEqual(
            [project["name"] for project in projects],
            ["Windchill Developer", "Robotics Process Automation"],
        )
        self.assertEqual(
            projects[0]["achievements"],
            [
                "Worked on OIR, lifecycle, document, product templates, Acls.",
                "Developed custom user picker for global attributes.",
                "Worked with existing utilities for creating users, groups and roles.",
            ],
        )
        self.assertEqual(
            projects[1]["achievements"],
            ["Built and maintained automation workflows."],
        )

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
                json.dumps(
                    {
                        "changeToken": "revision:revision-1",
                        "parserVersion": sync_google_doc.SYNC_PARSER_VERSION,
                    }
                ),
                encoding="utf-8",
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

    def test_skips_export_when_revision_is_missing_and_content_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            profile_path = root / "profile.json"
            resume_path = root / "resume.pdf"
            state_path = root / "sync-state.json"
            document = {
                "body": {
                    "content": [
                        {"paragraph": {"elements": [{"textRun": {"content": "Resume"}}]}}
                    ]
                }
            }
            profile_path.write_text('{"projects": []}\n', encoding="utf-8")
            resume_path.write_bytes(b"%PDF-existing")
            state_path.write_text(
                json.dumps(
                    {
                        "changeToken": sync_google_doc.document_change_token(document),
                        "parserVersion": sync_google_doc.SYNC_PARSER_VERSION,
                    }
                ),
                encoding="utf-8",
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
                sync_google_doc, "fetch_google_doc", return_value=document
            ), patch.object(
                sync_google_doc, "fetch_google_doc_pdf"
            ) as export_pdf:
                sync_google_doc.main()

            export_pdf.assert_not_called()


if __name__ == "__main__":
    unittest.main()

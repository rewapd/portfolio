import unittest

from scripts.sync_resume_projects import merge_projects, parse_project_section


class ResumeProjectParsingTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "google_scholar_crawler"))

from publish_results import PublishError, RESULT_FILENAMES, load_results, publish_results
from main import get_author_id


def git(arguments, cwd):
    return subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        check=True,
        text=True,
        capture_output=True,
    )


def write_results(directory: Path, citations=100, h_index=10, i10_index=8, publications=20):
    directory.mkdir(parents=True, exist_ok=True)
    payloads = {
        "gs_data.json": {
            "name": "测试作者",
            "updated": "2026-08-26T00:00:00+00:00",
            "publications": {},
        },
        "gs_data_total_citation.json": {
            "schemaVersion": 1,
            "label": "citations",
            "message": str(citations),
        },
        "gs_data_h_index.json": {
            "schemaVersion": 1,
            "label": "h-index",
            "message": str(h_index),
        },
        "gs_data_i10_index.json": {
            "schemaVersion": 1,
            "label": "i10-index",
            "message": str(i10_index),
        },
        "gs_data_total_publications.json": {
            "schemaVersion": 1,
            "label": "total-publications",
            "message": str(publications),
        },
    }
    for filename, payload in payloads.items():
        with (directory / filename).open("w", encoding="utf-8") as result_file:
            json.dump(payload, result_file)


class PublishResultsTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.remote = self.root / "remote.git"
        self.source = self.root / "source"
        git(["init", "--bare", str(self.remote)], cwd=self.root)
        git(["init", str(self.source)], cwd=self.root)
        git(["config", "user.name", "Test User"], cwd=self.source)
        git(["config", "user.email", "test@example.com"], cwd=self.source)
        (self.source / "README.md").write_text("source branch", encoding="utf-8")
        git(["add", "README.md"], cwd=self.source)
        git(["commit", "-m", "Initial source commit"], cwd=self.source)
        git(["remote", "add", "origin", str(self.remote)], cwd=self.source)
        git(["push", "origin", "HEAD:refs/heads/main"], cwd=self.source)

    def tearDown(self):
        self.temporary_directory.cleanup()

    def remote_files(self):
        result = git(
            ["--git-dir", str(self.remote), "ls-tree", "-r", "--name-only", "google-scholar-stats"],
            cwd=self.root,
        )
        return tuple(line for line in result.stdout.splitlines() if line)

    def test_publish_newer_results_only_updates_stats_branch(self):
        results = self.root / "results"
        write_results(results)
        branch_before = git(["branch", "--show-current"], cwd=self.source).stdout.strip()
        status_before = git(["status", "--porcelain"], cwd=self.source).stdout

        publish_results(results, repository=self.source)

        self.assertEqual(set(self.remote_files()), set(RESULT_FILENAMES))
        self.assertEqual(git(["branch", "--show-current"], cwd=self.source).stdout.strip(), branch_before)
        self.assertEqual(git(["status", "--porcelain"], cwd=self.source).stdout, status_before)

    def test_equal_or_lower_metrics_require_force(self):
        original = self.root / "original"
        write_results(original, citations=100, h_index=10, i10_index=8, publications=20)
        publish_results(original, repository=self.source)

        with self.assertRaises(PublishError):
            publish_results(original, repository=self.source)

        lower = self.root / "lower"
        write_results(lower, citations=99, h_index=10, i10_index=8, publications=20)
        with self.assertRaises(PublishError):
            publish_results(lower, repository=self.source)
        publish_results(lower, repository=self.source, force=True)

    def test_invalid_local_results_are_rejected(self):
        results = self.root / "results"
        write_results(results)
        (results / "gs_data_i10_index.json").unlink()
        with self.assertRaises(PublishError):
            load_results(results)

        write_results(results)
        (results / "gs_data_total_citation.json").write_text("not json", encoding="utf-8")
        with self.assertRaises(PublishError):
            load_results(results)

    def test_invalid_badge_schema_is_rejected(self):
        results = self.root / "results"
        write_results(results)
        with (results / "gs_data_h_index.json").open("w", encoding="utf-8") as result_file:
            json.dump({"schemaVersion": 1, "label": "wrong", "message": "10"}, result_file)
        with self.assertRaises(PublishError):
            load_results(results)

    def test_missing_remote_result_file_is_rejected(self):
        incomplete = self.root / "incomplete-stats"
        git(["init", str(incomplete)], cwd=self.root)
        git(["config", "user.name", "Test User"], cwd=incomplete)
        git(["config", "user.email", "test@example.com"], cwd=incomplete)
        (incomplete / "gs_data.json").write_text("{}", encoding="utf-8")
        git(["add", "gs_data.json"], cwd=incomplete)
        git(["commit", "-m", "Incomplete stats"], cwd=incomplete)
        git(["remote", "add", "origin", str(self.remote)], cwd=incomplete)
        git(["push", "origin", "HEAD:refs/heads/google-scholar-stats"], cwd=incomplete)

        results = self.root / "results"
        write_results(results)
        with self.assertRaises(PublishError):
            publish_results(results, repository=self.source, force=True)

    def test_author_id_argument_overrides_environment(self):
        with patch.dict(os.environ, {"GOOGLE_SCHOLAR_ID": "from-environment"}):
            self.assertEqual(get_author_id("from-argument"), "from-argument")
            self.assertEqual(get_author_id(), "from-environment")


if __name__ == "__main__":
    unittest.main()

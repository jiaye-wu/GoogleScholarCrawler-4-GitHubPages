"""Validate and publish locally fetched Google Scholar results."""

import argparse
import json
import shutil
import subprocess
import tempfile
from pathlib import Path


RESULT_FILENAMES = (
    "gs_data.json",
    "gs_data_total_citation.json",
    "gs_data_h_index.json",
    "gs_data_i10_index.json",
    "gs_data_total_publications.json",
)
BADGE_FILES = {
    "gs_data_total_citation.json": "citations",
    "gs_data_h_index.json": "h-index",
    "gs_data_i10_index.json": "i10-index",
    "gs_data_total_publications.json": "total-publications",
}


class PublishError(RuntimeError):
    """Raised when local results cannot be safely published."""


def run_git(arguments, *, cwd, check=True):
    result = subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise PublishError(f"git {' '.join(arguments)} failed: {detail}")
    return result


def load_results(results_dir: Path) -> dict:
    results = {}
    for filename in RESULT_FILENAMES:
        path = results_dir / filename
        if not path.is_file():
            raise PublishError(f"Missing required result file: {path}")
        try:
            with path.open(encoding="utf-8") as result_file:
                results[filename] = json.load(result_file)
        except (OSError, json.JSONDecodeError) as exc:
            raise PublishError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(results["gs_data.json"], dict):
        raise PublishError("gs_data.json must contain a JSON object.")
    for filename, label in BADGE_FILES.items():
        badge = results[filename]
        if not isinstance(badge, dict):
            raise PublishError(f"{filename} must contain a JSON object.")
        if badge.get("schemaVersion") != 1 or badge.get("label") != label:
            raise PublishError(f"{filename} does not match the expected badge schema.")
        try:
            value = int(str(badge["message"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise PublishError(f"{filename} has an invalid numeric message.") from exc
        if value < 0:
            raise PublishError(f"{filename} cannot contain a negative metric.")
    return results


def metrics(results: dict) -> dict:
    return {label: int(str(results[filename]["message"])) for filename, label in BADGE_FILES.items()}


def get_repository_root() -> Path:
    result = run_git(["rev-parse", "--show-toplevel"], cwd=Path.cwd())
    return Path(result.stdout.strip())


def get_remote_url(repository: Path, remote: str) -> str:
    return run_git(["remote", "get-url", remote], cwd=repository).stdout.strip()


def read_remote_results(remote_url: str, branch: str) -> tuple[dict | None, str | None]:
    ref = f"refs/heads/{branch}"
    probe = run_git(["ls-remote", "--heads", remote_url, ref], cwd=Path.cwd(), check=False)
    if probe.returncode:
        detail = probe.stderr.strip()
        if detail:
            raise PublishError(f"Could not inspect remote branch {branch}: {detail}")
        return None, None
    if not probe.stdout.strip():
        return None, None
    remote_oid = probe.stdout.split()[0]

    with tempfile.TemporaryDirectory(prefix="gh-scholar-read-") as directory:
        temporary_repository = Path(directory)
        run_git(["init", "-q"], cwd=temporary_repository)
        run_git(["remote", "add", "origin", remote_url], cwd=temporary_repository)
        run_git(
            ["fetch", "--quiet", "origin", f"{ref}:refs/remotes/origin/{branch}"],
            cwd=temporary_repository,
        )
        remote_results = {}
        for filename in RESULT_FILENAMES:
            result = run_git(
                ["show", f"refs/remotes/origin/{branch}:{filename}"],
                cwd=temporary_repository,
            )
            try:
                remote_results[filename] = json.loads(result.stdout or "")
            except (TypeError, json.JSONDecodeError) as exc:
                raise PublishError(f"Remote {filename} is not valid JSON.") from exc

    # Reuse the same validation rules for local and remote result payloads.
    with tempfile.TemporaryDirectory(prefix="gh-scholar-validate-") as directory:
        temporary_results = Path(directory)
        for filename, payload in remote_results.items():
            with (temporary_results / filename).open("w", encoding="utf-8") as result_file:
                json.dump(payload, result_file)
        load_results(temporary_results)
    return remote_results, remote_oid


def freshness_status(local: dict, remote: dict) -> tuple[bool, list[tuple[str, int, int]]]:
    local_metrics = metrics(local)
    remote_metrics = metrics(remote)
    comparison = [
        (label, local_metrics[label], remote_metrics[label])
        for label in BADGE_FILES.values()
    ]
    is_newer = all(local_value >= remote_value for _, local_value, remote_value in comparison)
    is_newer = is_newer and any(local_value > remote_value for _, local_value, remote_value in comparison)
    return is_newer, comparison


def print_comparison(comparison: list[tuple[str, int, int]]) -> None:
    print("Metric comparison (local vs remote):")
    for label, local_value, remote_value in comparison:
        print(f"  {label}: {local_value} vs {remote_value}")


def publish_results(
    results_dir: Path,
    remote: str = "origin",
    branch: str = "google-scholar-stats",
    message: str = "Updated Citation Data",
    force: bool = False,
    repository: Path | None = None,
) -> None:
    results_dir = results_dir.resolve()
    local_results = load_results(results_dir)
    repository = repository or get_repository_root()
    remote_url = get_remote_url(repository, remote)
    remote_results, remote_oid = read_remote_results(remote_url, branch)

    if remote_results is not None:
        is_newer, comparison = freshness_status(local_results, remote_results)
        print_comparison(comparison)
        if not is_newer and not force:
            raise PublishError(
                "Local results are not strictly newer. Use --force to override this warning."
            )
        if not is_newer:
            print("Warning: publishing with --force despite the freshness check.")
    else:
        print(f"Remote branch {branch!r} does not exist; creating it.")

    with tempfile.TemporaryDirectory(prefix="gh-scholar-publish-") as directory:
        temporary_repository = Path(directory)
        run_git(["init", "-q"], cwd=temporary_repository)
        run_git(["config", "user.name", "GH-ScholarBot local publisher"], cwd=temporary_repository)
        run_git(["config", "user.email", "noreply@users.noreply.github.com"], cwd=temporary_repository)
        for filename in RESULT_FILENAMES:
            shutil.copy2(results_dir / filename, temporary_repository / filename)
        run_git(["add", *RESULT_FILENAMES], cwd=temporary_repository)
        run_git(["commit", "-m", message], cwd=temporary_repository)
        run_git(["remote", "add", "target", remote_url], cwd=temporary_repository)
        lease = f"refs/heads/{branch}:{remote_oid or ''}"
        run_git(
            [
                "push",
                "target",
                f"HEAD:refs/heads/{branch}",
                f"--force-with-lease={lease}",
            ],
            cwd=temporary_repository,
        )
    print(f"Published {len(RESULT_FILENAMES)} files to {remote}/{branch}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish locally fetched Google Scholar results.")
    parser.add_argument("--results-dir", type=Path, default=Path(__file__).parent / "results")
    parser.add_argument("--remote", default="origin")
    parser.add_argument("--branch", default="google-scholar-stats")
    parser.add_argument("--message", default="Updated Citation Data")
    parser.add_argument("--force", action="store_true", help="Bypass the freshness warning.")
    args = parser.parse_args()
    try:
        publish_results(
            args.results_dir,
            remote=args.remote,
            branch=args.branch,
            message=args.message,
            force=args.force,
        )
    except PublishError as exc:
        parser.exit(1, f"Publish failed: {exc}\n")


if __name__ == "__main__":
    main()

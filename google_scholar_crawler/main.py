import argparse
import json
import os
import random
import signal
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from scholarly import ProxyGenerator, scholarly


MAX_ATTEMPTS = 3
RETRY_DELAYS_SECONDS = (15, 45)
SCHOLAR_REQUEST_TIMEOUT_SECONDS = 15
SCHOLAR_REQUEST_RETRIES = 2
ATTEMPT_TIMEOUT_SECONDS = 8 * 60
RESULTS_DIR = Path("results")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_author_id(cli_author_id: str | None = None) -> str:
    author_id = cli_author_id or os.environ.get("GOOGLE_SCHOLAR_ID")
    if not author_id:
        raise RuntimeError("Set GOOGLE_SCHOLAR_ID or pass --author-id.")
    return author_id


def configure_scholarly() -> None:
    """Keep individual Scholar requests and library retries bounded."""
    scholarly.set_timeout(SCHOLAR_REQUEST_TIMEOUT_SECONDS)
    scholarly.set_retries(SCHOLAR_REQUEST_RETRIES)
    print(
        "Configured scholarly: "
        f"request timeout={SCHOLAR_REQUEST_TIMEOUT_SECONDS}s, "
        f"retries={SCHOLAR_REQUEST_RETRIES}."
    )


@contextmanager
def attempt_timeout(seconds: int):
    """Interrupt a stuck Scholar operation on Linux runners.

    The external workflow timeout remains the cross-platform safety net. SIGALRM
    lets GitHub Actions retry a single stuck operation before that final limit.
    """
    if not hasattr(signal, "SIGALRM"):
        yield
        return

    def raise_timeout(_signum, _frame):
        raise TimeoutError(f"Scholar attempt exceeded {seconds} seconds.")

    previous_handler = signal.signal(signal.SIGALRM, raise_timeout)
    signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def configure_free_proxy(author_id: str):
    """Configure and test a free proxy, or fail so the fallback workflow runs."""
    proxy_generator = ProxyGenerator()
    try:
        with attempt_timeout(ATTEMPT_TIMEOUT_SECONDS):
            if not proxy_generator.FreeProxies():
                raise RuntimeError("No working free proxy was found.")
            scholarly.use_proxy(proxy_generator)
            print("Testing free proxy...")
            author = scholarly.search_author_id(author_id)
        print("Free proxy works, using it.")
        return author
    except Exception as exc:
        raise RuntimeError(f"Free proxy setup or test failed: {exc}") from exc


def fetch_author_once(author_id: str, initial_author=None):
    """Perform one Scholar lookup and fill operation."""
    author = initial_author
    if author is None:
        print("Looking up author profile...")
        author = scholarly.search_author_id(author_id)
    print("Filling author metadata, metrics, and publications...")
    scholarly.fill(author, sections=["basics", "indices", "counts", "publications"])
    return author


def fetch_author_in_subprocess(author_id: str):
    """Fetch directly in an isolated process with a reliable hard limit."""
    with tempfile.TemporaryDirectory() as temporary_directory:
        output_path = Path(temporary_directory) / "author.json"
        command = [
            sys.executable,
            "-u",
            str(Path(__file__).resolve()),
            "--author-id",
            author_id,
            "--fetch-once-output",
            str(output_path),
        ]
        popen_options = {}
        if os.name == "posix":
            popen_options["start_new_session"] = True
        elif os.name == "nt":
            popen_options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
        process = subprocess.Popen(command, **popen_options)
        try:
            return_code = process.wait(timeout=ATTEMPT_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as exc:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                subprocess.run(
                    ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            raise TimeoutError(
                f"Scholar attempt exceeded {ATTEMPT_TIMEOUT_SECONDS} seconds."
            ) from exc
        if return_code != 0:
            raise RuntimeError(f"Isolated Scholar attempt exited with code {return_code}.")
        with output_path.open(encoding="utf-8") as output_file:
            return json.load(output_file)


def fetch_author(author_id: str, initial_author=None):
    author = initial_author
    for attempt in range(MAX_ATTEMPTS):
        try:
            print(f"Fetching author (attempt {attempt + 1}/{MAX_ATTEMPTS}): {now()}")
            if author is None:
                author = fetch_author_in_subprocess(author_id)
            else:
                with attempt_timeout(ATTEMPT_TIMEOUT_SECONDS):
                    author = fetch_author_once(author_id, author)
            print(f"Finished fetching author: {now()}")
            return author
        except Exception as exc:
            author = None
            print(f"Attempt {attempt + 1} failed ({type(exc).__name__}): {exc}")
            if attempt == MAX_ATTEMPTS - 1:
                raise RuntimeError(f"Failed after {MAX_ATTEMPTS} attempts.") from exc
            delay = RETRY_DELAYS_SECONDS[attempt] + random.uniform(0, 10)
            print(f"Waiting {delay:.1f} seconds before retrying...")
            time.sleep(delay)


def write_json_atomically(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=path.parent, delete=False
    ) as temporary_file:
        json.dump(value, temporary_file, ensure_ascii=False, indent=2)
        temporary_name = temporary_file.name
    os.replace(temporary_name, path)


def save_results(author: dict) -> None:
    publications = author.get("publications", [])
    publication_map = {}
    missing_ids = 0
    duplicate_ids = 0
    for publication in publications:
        publication_id = publication.get("author_pub_id")
        if not publication_id:
            missing_ids += 1
        elif publication_id in publication_map:
            duplicate_ids += 1
        else:
            publication_map[publication_id] = publication
    if missing_ids or duplicate_ids:
        print(f"Publication IDs skipped: missing={missing_ids}, duplicate={duplicate_ids}.")

    author["updated"] = now()
    author["publications"] = publication_map
    write_json_atomically(RESULTS_DIR / "gs_data.json", author)

    badges = {
        "gs_data_total_citation.json": ("citations", author.get("citedby", 0)),
        "gs_data_h_index.json": ("h-index", author.get("hindex", 0)),
        "gs_data_i10_index.json": ("i10-index", author.get("i10index", 0)),
        "gs_data_total_publications.json": ("total-publications", len(publication_map)),
    }
    for filename, (label, value) in badges.items():
        write_json_atomically(
            RESULTS_DIR / filename,
            {"schemaVersion": 1, "label": label, "message": str(value)},
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Google Scholar author data.")
    parser.add_argument(
        "--use-free-proxy",
        action="store_true",
        help="Require a tested free proxy; exit non-zero when none is available.",
    )
    parser.add_argument(
        "--author-id",
        help="Google Scholar author ID; overrides GOOGLE_SCHOLAR_ID.",
    )
    parser.add_argument(
        "--test-free-proxy",
        action="store_true",
        help="Test a free proxy without writing result files.",
    )
    parser.add_argument(
        "--fetch-once-output",
        type=Path,
        help=argparse.SUPPRESS,
    )
    args = parser.parse_args()
    if args.test_free_proxy and not args.use_free_proxy:
        parser.error("--test-free-proxy requires --use-free-proxy.")
    author_id = get_author_id(args.author_id)
    configure_scholarly()

    if args.fetch_once_output:
        author = fetch_author_once(author_id)
        write_json_atomically(args.fetch_once_output, author)
        print("Isolated direct fetch completed successfully.")
        return

    initial_author = None
    if args.use_free_proxy:
        initial_author = configure_free_proxy(author_id)
        if args.test_free_proxy:
            print("Free proxy test completed successfully; no files were written.")
            return
    else:
        print("Using runner IP (no proxy).")

    save_results(fetch_author(author_id, initial_author))
    print("Data fetching and processing complete.")


if __name__ == "__main__":
    main()

# GH-ScholarBot

GH-ScholarBot fetches a Google Scholar profile and publishes cached statistics to a dedicated Git branch. Your website or README can then read stable JSON files instead of querying Google Scholar during every build.

This project began as a crawler extracted from the [AcadHomepage](https://github.com/RayeRen/acad-homepage.github.io) theme. It is now a standalone tool with local publishing, GitHub Actions automation, cached citation badges, h-index, i10-index, and publication-count support.

## Badge preview

**Total citations:** <a href="https://scholar.google.com/citations?user=D2n8tswAAAAAJ"><img src="https://img.shields.io/endpoint?logo=Google%20Scholar&url=https%3A%2F%2Fcdn.jsdelivr.net%2Fgh%2Fjiaye-wu%2FGH-ScholarBot@google-scholar-stats%2Fgs_data_total_citation.json&labelColor=f6f6f6&color=9cf&style=flat&label=citations" alt="Google Scholar citations"></a>

**Total publications:** <a href="https://scholar.google.com/citations?user=D2n8tswAAAAAJ"><img src="https://img.shields.io/endpoint?logo=Google%20Scholar&url=https%3A%2F%2Fcdn.jsdelivr.net%2Fgh%2Fjiaye-wu%2FGH-ScholarBot@google-scholar-stats%2Fgs_data_total_publications.json&labelColor=f6f6f6&color=9cf&style=flat&label=publications" alt="Google Scholar publications"></a>

**h-index:** <a href="https://scholar.google.com/citations?user=D2n8tswAAAAAJ"><img src="https://img.shields.io/endpoint?logo=Google%20Scholar&url=https%3A%2F%2Fcdn.jsdelivr.net%2Fgh%2Fjiaye-wu%2FGH-ScholarBot@google-scholar-stats%2Fgs_data_h_index.json&labelColor=f6f6f6&color=9cf&style=flat&label=h-index" alt="Google Scholar h-index"></a>

**i10-index:** <a href="https://scholar.google.com/citations?user=D2n8tswAAAAAJ"><img src="https://img.shields.io/endpoint?logo=Google%20Scholar&url=https%3A%2F%2Fcdn.jsdelivr.net%2Fgh%2Fjiaye-wu%2FGH-ScholarBot@google-scholar-stats%2Fgs_data_i10_index.json&labelColor=f6f6f6&color=9cf&style=flat&label=i10-index" alt="Google Scholar i10-index"></a>

## What it publishes

Every successful update replaces the contents of the `google-scholar-stats` branch with these files:

| File | Purpose |
| --- | --- |
| `gs_data.json` | Full Google Scholar author and publication data. |
| `gs_data_total_citation.json` | Shield.io endpoint for total citations. |
| `gs_data_h_index.json` | Shield.io endpoint for h-index. |
| `gs_data_i10_index.json` | Shield.io endpoint for i10-index. |
| `gs_data_total_publications.json` | Shield.io endpoint for publication count. |

The JSON filenames and badge schemas are stable. Existing badge URLs continue to work.

## Quick start: local update

Local updates are the recommended path when Google blocks GitHub-hosted runners but permits requests from your own network.

Prerequisites:

- Python 3.10 or newer
- Git
- An authenticated `origin` remote with permission to push to the repository

From the repository root, run the following.

Windows PowerShell:

```powershell
cd google_scholar_crawler
python -m pip install -r requirements.txt
python main.py --author-id YOUR_GOOGLE_SCHOLAR_ID
python publish_results.py
```

macOS/Linux:

```bash
cd google_scholar_crawler
python3 -m pip install -r requirements.txt
python3 main.py --author-id YOUR_GOOGLE_SCHOLAR_ID
python3 publish_results.py
```

`YOUR_GOOGLE_SCHOLAR_ID` is the value after `user=` in your public Google Scholar profile URL. You may instead set `GOOGLE_SCHOLAR_ID`; `--author-id` takes precedence.

The crawler writes results to `google_scholar_crawler/results/`. That directory is ignored by Git. `publish_results.py` reads the repository's current `origin` URL, creates a temporary Git repository, and publishes only the five result files. It never checks out another branch or changes your current worktree.

### Safe publication rules

Before pushing, the publisher validates all five JSON files and compares four metrics with the remote `google-scholar-stats` branch:

- citations
- h-index
- i10-index
- total publications

The default rule accepts a publish only when every local metric is at least as high as its remote value and at least one metric is higher. This helps prevent an incomplete or blocked fetch from replacing good cached data.

If Google Scholar has corrected data downward, or you deliberately need to publish unchanged data, review the displayed comparison and run:

```bash
python publish_results.py --force
```

`--force` bypasses the freshness warning only. JSON validation remains mandatory, and the final push uses a Git lease so a concurrent update is not overwritten silently.

Useful publisher options:

```bash
python publish_results.py --help
python publish_results.py --remote upstream
python publish_results.py --branch my-stats-branch
python publish_results.py --results-dir path/to/results
```

## GitHub Actions automation

Automation remains available as a supplementary update path. Configure the `GOOGLE_SCHOLAR_ID` repository secret before running it.

| Workflow | Trigger | Behavior |
| --- | --- | --- |
| **Get Citation Data (with free proxy)** | Every Sunday at 02:42 UTC, or manually | Primary automatic update using a free proxy. |
| **Get Citation Data (without free proxy fallback)** | Manually, or after the proxy workflow fails | Direct-access fallback. |
| **Test Free Proxy** | Manually only | Tests free-proxy availability without writing JSON or publishing data. |

The crawler has bounded request retries and process timeouts so blocked requests fail visibly instead of consuming the entire GitHub Actions job limit. A successful Actions run and a successful local publish update the same `google-scholar-stats` branch.

## Use the cached data on a website

Set the following in your Jekyll `_config.yml`:

```yaml
repository: "<github-user>/<repository>"
google_scholar_stats_use_cdn: true
```

Set `google_scholar_stats_use_cdn` to `false` to read directly from GitHub instead of jsDelivr. CDN propagation can take time after an update.

Use a Shield.io endpoint badge in Markdown or HTML. Replace `<github-user>`, `<repository>`, and `YOUR_GOOGLE_SCHOLAR_ID`:

```html
<a href="https://scholar.google.com/citations?user=YOUR_GOOGLE_SCHOLAR_ID">
  <img src="https://img.shields.io/endpoint?logo=Google%20Scholar&url=https%3A%2F%2Fcdn.jsdelivr.net%2Fgh%2F<github-user>%2F<repository>@google-scholar-stats%2Fgs_data_total_citation.json&labelColor=f6f6f6&color=9cf&style=flat&label=citations" alt="Google Scholar citations">
</a>
```

Replace `gs_data_total_citation.json` with one of the other badge JSON filenames to display h-index, i10-index, or publication count. If you do not use jsDelivr, replace the encoded `https://cdn.jsdelivr.net/gh/` URL with the corresponding `https://github.com/` URL.

## Deployment choices

### Standalone repository

Fork this repository, set `_config.yml` to your fork, configure the `GOOGLE_SCHOLAR_ID` secret only if you want Actions automation, and use the branch files from that fork in your website badges.

### Integrated into a website repository

Copy the crawler directory, workflows, `.gitignore` rule, and relevant `_config.yml` settings into your website repository. Set `repository` to that website repository. Both local publishing and Actions then update its `google-scholar-stats` branch.

For Actions publishing, enable **Settings → Actions → General → Workflow permissions → Read and write permissions** in the target repository.

## Manual Git publishing

`publish_results.py` is preferred because it validates JSON and checks metric freshness. For an advanced manual alternative, create a temporary directory outside your working repository, copy only the five files from `google_scholar_crawler/results/`, and run:

```bash
git init
git config user.name "GH-ScholarBot local publisher"
git config user.email "noreply@users.noreply.github.com"
git add gs_data.json gs_data_total_citation.json gs_data_h_index.json gs_data_i10_index.json gs_data_total_publications.json
git commit -m "Updated Citation Data"
git remote add origin YOUR_REPOSITORY_REMOTE_URL
git push origin HEAD:google-scholar-stats --force
```

This intentionally replaces the stats branch contents. It does not include the freshness protection provided by `publish_results.py`.

## Troubleshooting

### GitHub Actions cannot fetch Scholar data

Google Scholar frequently blocks cloud-runner IP ranges and free proxies may be unavailable. Try a local update first. You can also run **Test Free Proxy** to distinguish proxy availability from general Scholar blocking.

### The publisher refuses to push

Read the metric comparison. Equal or lower values require `--force`; malformed, missing, or schema-invalid JSON files cannot be published. Ensure that `git push` to `origin` works with your local credentials.

### Local crawl is blocked or times out

Retry later, try a different network, or consider a paid proxy. Use `python main.py --use-free-proxy --author-id YOUR_GOOGLE_SCHOLAR_ID` only when you explicitly want the free-proxy mode.

## Development

Run the offline publisher test suite after installing crawler dependencies:

```bash
python -m unittest discover -s tests -v
```

See [CHANGELOG.md](CHANGELOG.md) for version history.

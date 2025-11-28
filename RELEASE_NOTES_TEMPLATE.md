# Release Notes Template

Use this template when creating new releases on GitHub. The release notes will be displayed on the Releases page and sent to PyPI.

## Format

```markdown
## What's New

Brief description of major changes and features.

## Features
- New feature 1
- New feature 2

## Bug Fixes
- Fixed issue X
- Fixed issue Y

## Breaking Changes
(if any)
- Change 1: Impact and migration path

## Deprecations
(if any)
- Deprecated feature X (use Y instead)

## Install

```bash
pip install --upgrade logcost
```

## Contributors
@username1 @username2
```

## Historical Release Notes

### v0.1.4
```
## What's New
Updated documentation to reflect PyPI availability.

## Features
- Easy installation via `pip install logcost`

## Changes
- Updated README with PyPI installation instructions
- Added init container example for Kubernetes file permissions
- Documented sidecar file permission requirements

## Install
```bash
pip install logcost==0.1.4
```
```

### v0.1.3
```
## What's New
Initial PyPI release! LogCost is now available on the Python Package Index.

## Features
- **Zero-config tracking** - Monkey-patches logging module automatically
- **Aggregation by location** - Groups logs by file:line:level
- **Thread-safe** - Works with concurrent applications
- **Framework support** - Flask, FastAPI, Django, Kubernetes examples
- **CLI tools** - analyze, report, estimate, diff, capture commands
- **Export options** - JSON, CSV, Prometheus, HTML reports
- **Cost analysis** - GCP, AWS, Azure cost estimates
- **Slack integration** - Hourly notifications with trends
- **GCloud attribution** - Preserves actual source file:line

## Install
```bash
pip install logcost==0.1.3
```

## Quick Start
```bash
pip install logcost
```

```python
import logcost
import logging

logger = logging.getLogger(__name__)
logger.info("Your message here")

# Export stats
logcost.export("/tmp/logcost_stats.json")
```

```bash
# Analyze costs
python -m logcost.cli analyze /tmp/logcost_stats.json --provider gcp --top 5
```

## Documentation
- Full documentation: https://github.com/ubermorgenland/LogCost#readme
- Examples: https://github.com/ubermorgenland/LogCost/tree/master/examples
- PyPI: https://pypi.org/project/logcost/
```

## Release Checklist

Before creating a release:

- [ ] Version bumped in `pyproject.toml`
- [ ] `pyproject.toml` committed and pushed
- [ ] CI/CD tests passing on master
- [ ] `CHANGELOG.md` updated (optional but recommended)
- [ ] Release notes prepared using this template
- [ ] Ready to run: `gh release create vX.Y.Z --title "LogCost X.Y.Z" --notes "..."`

## Automated Publishing

Once you create a release using `gh release create`, the GitHub Actions workflow `.github/workflows/publish-to-pypi.yml` will:

1. Build distribution packages
2. Publish to PyPI
3. Version becomes available via `pip install logcost==X.Y.Z`

**Note**: Make sure the `PYPI_API_TOKEN` secret is configured in GitHub Settings → Secrets.

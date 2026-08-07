# Linting and Type Checking Guide

## Purpose

This project uses [ruff](https://docs.astral.sh/ruff/) for linting and [pyright](https://microsoft.github.io/pyright/)
for static type checking. Both run automatically on every pull request via the `lint-checks.yml` GitHub
Actions workflow, but that check is **advisory only** — it never fails the build. Findings show up as
inline warning annotations on the PR diff so reviewers and the PR author can see them, but it's each
student's responsibility to run these tools locally and address what they find before (or while) a PR is
open.

## Install on your host system

Both tools are listed in `requirements.txt`, so installing project dependencies installs them too:

```bash
python -m pip install -r requirements.txt
```

To install just the two tools (e.g. into a separate environment, or to confirm they're available):

```bash
python -m pip install ruff pyright
```

Confirm both are installed and check their versions:

```bash
ruff --version
pyright --version
```

## Run ruff locally

From the repository root:

```bash
# Check the pipeline service for lint issues
ruff check services

# Auto-fix what ruff can safely fix
ruff check --fix services

# Check formatting (ruff's formatter is separate from its linter)
ruff format --check services
ruff format services   # apply formatting
```

## Run pyright locally

Pyright needs the pipeline package on its search path, so point it at the `src` directory:

```bash
pyright services/pipeline/src
```

## What CI runs

The `lint-checks.yml` workflow (separate from the required `python-quality-gates.yml` and
`air-ticket-check.yml` checks) runs on every PR into `main`:

- `ruff check --output-format=github services`
- `pyright --outputjson services/pipeline/src`, with results converted to inline `::warning` annotations

Both steps use `continue-on-error`, so this workflow always reports success — it will never block a merge.
Treat its warnings the same way you'd treat a reviewer's comment: worth addressing, but not a gate.

There is no `pyproject.toml`, `ruff.toml`, or `pyrightconfig.json` in this repo yet, so both tools run with
their default settings. If the team decides on stricter or different rules later, add the corresponding
config file and update this doc.

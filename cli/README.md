# hiss CLI

Typer + httpx + rich client for the hiss API.

## Install

```
pip install -e cli/
hiss --help
```

## Usage

```
hiss --url http://localhost:8000 projects list
hiss projects create --key OPS --name "Operations"
hiss issues list --project OPS --status open
hiss comments add 42 "reproduced on staging"
hiss labels create bug
```

Base URL from `--url` flag or `HISS_URL` env (default `http://localhost:8000`).

Table output by default, `--json` on list commands.

# Changelog

## 1.1.0

- Base training pack rebuilt and expanded to 112 records: everyday conversation
  (greetings, small talk, politeness, plans, phone, travel, interviews) and
  English usage, plus a full Python section — running scripts, types, strings,
  loops, lists, dicts, comprehensions, sorting, functions, files, CSV, JSON,
  errors, modules, venv/pip, argparse, pathlib, subprocess, datetime, regex,
  classes, dataclasses, type hints, debugging and testing — with five complete
  recipes (word count, bulk rename, CSV summary, calculator, API fetch).
- `their`, `there`, `they`, `its` and `your` are no longer stopwords, so
  questions about those words find their records in both engines.
- Version 1.1.0 across the CLI, the browser build and the release assets.

## 1.0.0

First release of the ONYX CLI.

- Codex-style terminal app: banner, `›` prompt, slash commands, dim status lines.
- `onyx train` reads JSONL/JSON/text training data and saves the knowledge to
  `~/.onyx/knowledge.json`, so it survives restarts.
- Offline BM25 retrieval over trained records; answers cite their sources.
- Optional local model: `/model <base-url> <name>` or `ONYX_MODEL_URL` /
  `ONYX_MODEL` feeds retrieved records to any OpenAI-compatible server.
- `onyx ask`, `onyx knowledge`, `onyx forget`, `onyx version`.
- `basetrainer.txt`: generator prompt plus the training-data spec and example.
- `base-training.jsonl`: a 53-record base pack on basic conversation and
  English usage (greetings, small talk, politeness, tenses, homophones,
  spelling, email tone), shipped in `training/` and attached to the release.
- Browser build (`web/`) of the same app: no install and no SmartScreen
  prompt, Codex-style UI, JSONL training via file drop, picker or paste,
  knowledge saved in the browser with export/import of `onyx-knowledge.json`,
  and an optional local model. `web/public/onyx-core.js` ports the retrieval
  engine and ranks packs identically to the CLI.
- `.github/workflows/release.yml` builds Windows/Linux/macOS binaries for
  every `v*` tag and attaches them to the release.

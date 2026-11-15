# Changelog

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
- `.github/workflows/release.yml` builds Windows/Linux/macOS binaries for
  every `v*` tag and attaches them to the release.

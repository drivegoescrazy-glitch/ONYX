# ONYX

ONYX is the open source, locally hosted alternative to Claude Code: a coding agent that runs entirely on your own machine, with no subscription and no code leaving your device.

You teach it with training data you own. Training stores the knowledge in the app itself (`~/.onyx/knowledge.json`), so it is there every time you launch it.

```
╭────────────────────────────────────────────────────────────╮
│ >_ ONYX (v1.0.0)                                           │
│                                                            │
│ model:      knowledge-only (offline)                       │
│ knowledge:  7 records · 14.2 kB                            │
│ directory:  ~/projects/onyx                                │
│                                                            │
│ Ask a question, or type /help to see the commands.         │
╰────────────────────────────────────────────────────────────╯
```

## Build

Single static binary, standard library only (Go 1.22+):

```sh
go build -trimpath -ldflags "-s -w" -o onyx .
GOOS=windows GOARCH=amd64 go build -trimpath -ldflags "-s -w" -o onyx.exe .
```

Releases are cut by pushing a `v*` tag: `.github/workflows/release.yml` builds the Windows `.exe`, Linux and macOS binaries and attaches them to the GitHub release.

## Use

```sh
onyx                          # start the app
onyx train training.jsonl     # train, and save the knowledge to the app
onyx ask "how do i undo a commit?"
onyx knowledge                # what has the app learned?
onyx forget --yes             # delete trained knowledge
onyx version
```

Inside the app:

| command | what it does |
| --- | --- |
| `/train <path> [--replace]` | read training data and save it to the app |
| `/knowledge` | what the app has learned |
| `/status` | version, model and store details |
| `/model <url> <name>` | answer through any OpenAI-compatible local server |
| `/forget --yes` | delete all trained knowledge |
| `/clear` | redraw the screen |
| `/exit` | quit |

## Training data

JSONL, one record per line. Questions need `input` and `output`; reference
material uses `kind: "doc"` with `title` and `text`.

```json
{"id":"git-undo-last-commit","kind":"qa","input":"how do i undo the last commit but keep my changes?","output":"git reset --soft HEAD~1","tags":["git","commit","undo"],"source":"git-basics"}
```

`.json` (array or `{"records":[...]}`), `.txt` and `.md` files work too; plain
text is chunked into doc records. Aliases `question`/`answer`,
`prompt`/`completion`, `instruction`/`response` and OpenAI-style `messages`
are accepted, so packs written for other trainers usually load unchanged.

To generate a pack on any subject, give an AI [basetrainer.txt](basetrainer.txt)
and say what you want the data about. It is the complete prompt plus the spec
and a worked example.

## Local model (optional)

ONYX works offline with retrieval over your trained knowledge. To have answers
written instead of retrieved, connect a local OpenAI-compatible server:

```sh
/model http://127.0.0.1:11434/v1 llama3.1:8b
# or: ONYX_MODEL_URL=http://127.0.0.1:11434/v1 ONYX_MODEL=llama3.1:8b onyx
```

Trained records are handed to the model as ground truth. `ONYX_HOME` relocates
the store, `NO_COLOR` disables colour.

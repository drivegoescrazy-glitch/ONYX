"""Runnable Python recipes for the ONYX base pack.

Every recipe is a complete program with a `<<placeholder>>` that fills in from
`params`. `build_pack.py` compiles each generated script before it is written,
so nothing in the shipped pack is untested code.
"""

RECIPES = [
    {
        "name": "word count",
        "tags": ["python", "script", "files", "text"],
        "desc": "count the lines, words and characters in <<file>>",
        "params": [{"file": "notes.txt"}, {"file": "app.log"}, {"file": "book.md"}, {"file": "data.txt"}],
        "code": '''#!/usr/bin/env python3
"""Count the lines, words and characters in <<file>>."""

import sys
from pathlib import Path


def count(path):
    text = Path(path).read_text(encoding="utf-8")
    words = text.split()
    return {
        "lines": text.count("\\n") + (0 if text.endswith("\\n") or not text else 1),
        "words": len(words),
        "characters": len(text),
        "unique_words": len({word.lower().strip(".,!?;:'()") for word in words}),
    }


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "<<file>>"
    for name, value in count(path).items():
        print(f"{name:>14}: {value:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "word frequency",
        "tags": ["python", "script", "text", "collections"],
        "desc": "print the most common words in <<file>>",
        "params": [{"file": "notes.txt"}, {"file": "article.txt"}, {"file": "chat.log"}],
        "code": '''#!/usr/bin/env python3
"""Print the most common words in <<file>>."""

import re
import sys
from collections import Counter

STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "it", "that",
    "for", "on", "with", "as", "at", "be", "this", "by", "from", "was",
}


def top_words(path, limit=10):
    text = open(path, encoding="utf-8").read().lower()
    words = re.findall(r"[a-z']+", text)
    return Counter(w for w in words if w not in STOPWORDS).most_common(limit)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "<<file>>"
    for word, count in top_words(path):
        print(f"{word:<20} {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "filter csv rows",
        "tags": ["python", "script", "csv", "filter"],
        "desc": "filter the rows of <<file>> where the <<column>> column is above <<value>>",
        "params": [
            {"file": "sales.csv", "column": "amount", "value": "100"},
            {"file": "orders.csv", "column": "total", "value": "50"},
            {"file": "grades.csv", "column": "score", "value": "70"},
        ],
        "code": '''#!/usr/bin/env python3
"""Keep the rows of <<file>> whose <<column>> is above <<value>>."""

import csv
import sys
from pathlib import Path


def above(rows, column, floor):
    for row in rows:
        try:
            value = float((row.get(column) or "").replace(",", ""))
        except ValueError:
            continue
        if value > floor:
            yield row


def main():
    source = Path(sys.argv[1] if len(sys.argv) > 1 else "<<file>>")
    floor = float(sys.argv[2]) if len(sys.argv) > 2 else <<value>>
    with source.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    kept = list(above(rows, "<<column>>", floor))
    if not rows:
        print("no rows found")
        return 1
    target = source.with_name(source.stem + "-filtered.csv")
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(kept)
    print(f"{len(kept)} of {len(rows)} rows written to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "sum a csv column",
        "tags": ["python", "script", "csv", "numbers"],
        "desc": "sum the <<column>> column of <<file>>",
        "params": [
            {"file": "sales.csv", "column": "amount"},
            {"file": "expenses.csv", "column": "cost"},
            {"file": "timesheet.csv", "column": "hours"},
        ],
        "code": '''#!/usr/bin/env python3
"""Sum the <<column>> column of <<file>>."""

import csv
import sys


def total(path, column):
    value = 0.0
    rows = 0
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            raw = (row.get(column) or "").strip().replace(",", "")
            try:
                value += float(raw)
            except ValueError:
                continue
            rows += 1
    return value, rows


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "<<file>>"
    value, rows = total(path, "<<column>>")
    print(f"{rows} rows, total <<column>>: {value:,.2f}")
    print(f"average: {value / rows:,.2f}" if rows else "average: n/a")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "sort csv rows",
        "tags": ["python", "script", "csv", "sort"],
        "desc": "sort <<file>> by the <<column>> column",
        "params": [
            {"file": "sales.csv", "column": "amount"},
            {"file": "players.csv", "column": "score"},
            {"file": "stock.csv", "column": "price"},
        ],
        "code": '''#!/usr/bin/env python3
"""Sort <<file>> by <<column>>, biggest first."""

import csv
import sys


def sortable(value):
    try:
        return (0, float(value.replace(",", "")))
    except (AttributeError, ValueError):
        return (1, str(value).lower())


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "<<file>>"
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        print("no rows found")
        return 1
    rows.sort(key=lambda row: sortable(row.get("<<column>>", "")), reverse=True)
    target = path.rsplit(".", 1)[0] + "-sorted.csv"
    with open(target, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    for row in rows[:5]:
        print(row.get("<<column>>"), "-", row)
    print(f"{len(rows)} rows written to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "group csv and total",
        "tags": ["python", "script", "csv", "groupby"],
        "desc": "group <<file>> by <<key>> and total the <<column>> column",
        "params": [
            {"file": "sales.csv", "key": "region", "column": "amount"},
            {"file": "orders.csv", "key": "customer", "column": "total"},
            {"file": "hours.csv", "key": "project", "column": "hours"},
        ],
        "code": '''#!/usr/bin/env python3
"""Group <<file>> by <<key>> and total <<column>>."""

import csv
import sys
from collections import defaultdict


def summarise(path, key, column):
    totals = defaultdict(float)
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            raw = (row.get(column) or "").replace(",", "").strip()
            try:
                totals[row.get(key, "?")] += float(raw)
            except ValueError:
                continue
    return totals


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "<<file>>"
    totals = summarise(path, "<<key>>", "<<column>>")
    for name, value in sorted(totals.items(), key=lambda item: item[1], reverse=True):
        print(f"{name:<20} {value:>12,.2f}")
    print(f"\\n{len(totals)} groups, {sum(totals.values()):,.2f} total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "csv to json",
        "tags": ["python", "script", "csv", "json", "convert"],
        "desc": "convert <<file>> to JSON",
        "params": [{"file": "sales.csv"}, {"file": "contacts.csv"}, {"file": "inventory.csv"}],
        "code": '''#!/usr/bin/env python3
"""Convert <<file>> to a JSON array of objects."""

import csv
import json
import sys
from pathlib import Path


def convert(path):
    with Path(path).open(newline="", encoding="utf-8") as handle:
        rows = [dict(row) for row in csv.DictReader(handle)]
    target = Path(path).with_suffix(".json")
    target.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    return target, len(rows)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "<<file>>"
    target, count = convert(path)
    print(f"{count} rows written to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "json to csv",
        "tags": ["python", "script", "json", "csv", "convert"],
        "desc": "convert <<file>> to CSV",
        "params": [{"file": "data.json"}, {"file": "contacts.json"}, {"file": "locations.json"}],
        "code": '''#!/usr/bin/env python3
"""Convert a JSON array of objects in <<file>> to CSV."""

import csv
import json
import sys
from pathlib import Path


def convert(path):
    rows = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise SystemExit("expected a non-empty JSON array of objects")
    fields = list({key for row in rows for key in row})
    target = Path(path).with_suffix(".csv")
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return target, len(rows), fields


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "<<file>>"
    target, count, fields = convert(path)
    print(f"{count} rows, columns: {', '.join(fields)}")
    print(f"written to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "append timestamped line",
        "tags": ["python", "script", "logging", "files"],
        "desc": "append a timestamped line to <<file>>",
        "params": [{"file": "notes.log"}, {"file": "work.log"}, {"file": "journal.txt"}],
        "code": '''#!/usr/bin/env python3
"""Append a timestamped line to <<file>>."""

import sys
from datetime import datetime
from pathlib import Path

LOG = Path("<<file>>")


def log(message):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"{stamp}  {message}\\n")
    return stamp


def main():
    message = " ".join(sys.argv[1:]) or "started"
    print(f"[{log(message)}] {message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "rename files",
        "tags": ["python", "script", "files", "rename"],
        "desc": "rename the files in a folder with the prefix <<prefix>>",
        "params": [{"prefix": "holiday"}, {"prefix": "scan"}, {"prefix": "photo"}],
        "code": '''#!/usr/bin/env python3
"""Rename every file in a folder to <<prefix>>-001, <<prefix>>-002, ..."""

import argparse
from pathlib import Path


def rename(folder, apply):
    files = sorted(path for path in Path(folder).iterdir() if path.is_file())
    width = max(3, len(str(len(files))))
    for index, path in enumerate(files, start=1):
        target = path.with_name(f"<<prefix>>-{index:0{width}d}{path.suffix.lower()}")
        print(f"{path.name}  ->  {target.name}")
        if apply:
            path.rename(target)
    if not apply:
        print("\\nDry run. Add --apply to rename for real.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", nargs="?", default=".")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    rename(args.folder, args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "move files by type",
        "tags": ["python", "script", "files", "tidy"],
        "desc": "move the <<ext>> files in a folder into a subfolder",
        "params": [{"ext": ".png"}, {"ext": ".pdf"}, {"ext": ".csv"}, {"ext": ".jpg"}],
        "code": '''#!/usr/bin/env python3
"""Move every <<ext>> file in a folder into a matching subfolder."""

import argparse
import shutil
from pathlib import Path

EXTENSION = "<<ext>>"


def move(folder, apply):
    source = Path(folder)
    target = source / EXTENSION.lstrip(".")
    moved = 0
    for path in sorted(source.glob(f"*{EXTENSION}")):
        if not path.is_file():
            continue
        print(f"{path.name}  ->  {target.name}/")
        if apply:
            target.mkdir(exist_ok=True)
            shutil.move(str(path), target / path.name)
        moved += 1
    if not apply:
        print("\\nDry run. Add --apply to move the files.")
    return moved


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", nargs="?", default=".")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(f"{move(args.folder, args.apply)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "delete old files",
        "tags": ["python", "script", "files", "cleanup"],
        "desc": "delete <<ext>> files older than <<days>> days in a folder",
        "params": [
            {"ext": ".log", "days": "30"},
            {"ext": ".tmp", "days": "7"},
            {"ext": ".bak", "days": "14"},
        ],
        "code": '''#!/usr/bin/env python3
"""Delete <<ext>> files in a folder that are older than <<days>> days."""

import argparse
import time
from pathlib import Path

EXTENSION = "<<ext>>"
MAX_AGE = <<days>> * 24 * 60 * 60


def stale(folder):
    now = time.time()
    for path in sorted(Path(folder).glob(f"*{EXTENSION}")):
        if path.is_file() and now - path.stat().st_mtime > MAX_AGE:
            yield path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", nargs="?", default=".")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    victims = list(stale(args.folder))
    for path in victims:
        print(path)
        if args.apply:
            path.unlink()
    print(f"\\n{len(victims)} files", "(deleted)" if args.apply else "(dry run)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "backup by extension",
        "tags": ["python", "script", "files", "backup"],
        "desc": "back up every <<ext>> file in a folder",
        "params": [{"ext": ".py"}, {"ext": ".csv"}, {"ext": ".docx"}],
        "code": '''#!/usr/bin/env python3
"""Copy every <<ext>> file into a timestamped backup folder."""

import shutil
from datetime import datetime
from pathlib import Path

EXTENSION = "<<ext>>"


def backup(folder="."):
    source = Path(folder)
    target = source / f"backup-{datetime.now():%Y%m%d-%H%M%S}"
    target.mkdir(parents=True, exist_ok=True)
    copied = 0
    for path in sorted(source.glob(f"*{EXTENSION}")):
        if path.is_file():
            shutil.copy2(path, target / path.name)
            copied += 1
    return target, copied


def main():
    target, copied = backup()
    print(f"copied {copied} files to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "search files",
        "tags": ["python", "script", "files", "search"],
        "desc": "search the folder for files containing <<word>>",
        "params": [{"word": "TODO"}, {"word": "password"}, {"word": "error"}],
        "code": '''#!/usr/bin/env python3
"""Search every text file under a folder for the word <<word>>."""

import argparse
from pathlib import Path

SUFFIXES = {".txt", ".py", ".md", ".csv", ".json", ".log"}


def search(root, needle):
    for path in sorted(Path(root).rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUFFIXES:
            continue
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            continue
        for number, line in enumerate(lines, start=1):
            if needle.lower() in line.lower():
                yield f"{path}:{number}: {line.strip()}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    hits = list(search(args.root, "<<word>>"))
    print("\\n".join(hits))
    print(f"\\n{len(hits)} matches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "replace text in files",
        "tags": ["python", "script", "files", "replace"],
        "desc": "replace <<old>> with <<new>> in every text file in a folder",
        "params": [
            {"old": "colour", "new": "color"},
            {"old": "TODO", "new": "DONE"},
            {"old": "http://", "new": "https://"},
        ],
        "code": '''#!/usr/bin/env python3
"""Replace <<old>> with <<new>> in every text file under a folder."""

import argparse
from pathlib import Path

OLD = "<<old>>"
NEW = "<<new>>"
SUFFIXES = {".txt", ".py", ".md", ".csv", ".json", ".html", ".css"}


def rewrite(path, apply):
    text = path.read_text(encoding="utf-8", errors="ignore")
    if OLD not in text:
        return 0
    hits = text.count(OLD)
    print(f"{path}: {hits}")
    if apply:
        path.write_text(text.replace(OLD, NEW), encoding="utf-8")
    return hits


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", nargs="?", default=".")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    total = 0
    for path in sorted(Path(args.folder).rglob("*")):
        if path.is_file() and path.suffix.lower() in SUFFIXES:
            total += rewrite(path, args.apply)
    print(f"\\n{total} replacements", "" if args.apply else "(dry run)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "json config with defaults",
        "tags": ["python", "script", "json", "config"],
        "desc": "read settings from <<file>> with defaults",
        "params": [{"file": "settings.json"}, {"file": "config.json"}, {"file": "app.json"}],
        "code": '''#!/usr/bin/env python3
"""Load <<file>>, filling in defaults when keys are missing."""

import json
from pathlib import Path

SETTINGS = Path("<<file>>")
DEFAULTS = {"theme": "dark", "volume": 5, "recent": []}


def load():
    if not SETTINGS.exists():
        return dict(DEFAULTS)
    with SETTINGS.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return {**DEFAULTS, **data}


def save(settings):
    SETTINGS.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def main():
    settings = load()
    print("loaded:", settings)
    settings["recent"].append("onyx")
    save(settings)
    print("saved to", SETTINGS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "download file",
        "tags": ["python", "script", "network", "download"],
        "desc": "download <<url>> to disk",
        "params": [
            {"url": "https://example.com/data.csv"},
            {"url": "https://example.com/logo.png"},
        ],
        "code": '''#!/usr/bin/env python3
"""Download <<url>> in chunks instead of holding it in memory."""

import sys
import urllib.request
from pathlib import Path

CHUNK = 64 * 1024


def download(url, target=None):
    target = Path(target or url.rsplit("/", 1)[-1] or "download.bin")
    with urllib.request.urlopen(url, timeout=30) as response, target.open("wb") as out:
        total = 0
        while True:
            block = response.read(CHUNK)
            if not block:
                break
            out.write(block)
            total += len(block)
    return target, total


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "<<url>>"
    path, size = download(url)
    print(f"saved {path} ({size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "fetch json api",
        "tags": ["python", "script", "network", "json", "api"],
        "desc": "fetch JSON from <<url>> and print it",
        "params": [
            {"url": "https://api.github.com/repos/python/cpython"},
            {"url": "https://api.example.com/users"},
        ],
        "code": '''#!/usr/bin/env python3
"""Fetch JSON from <<url>>, with a timeout and a clear error."""

import json
import sys
import urllib.error
import urllib.request


def get_json(url, timeout=15):
    request = urllib.request.Request(url, headers={"User-Agent": "onyx-script/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "<<url>>"
    try:
        data = get_json(url)
    except urllib.error.HTTPError as error:
        print(f"HTTP {error.code}: {error.reason}")
        return 1
    except urllib.error.URLError as error:
        print(f"network error: {error.reason}")
        return 1
    print(json.dumps(data, indent=2, ensure_ascii=False)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "parse log levels",
        "tags": ["python", "script", "text", "regex", "logging"],
        "desc": "count the error levels in <<file>>",
        "params": [{"file": "app.log"}, {"file": "server.log"}, {"file": "build.log"}],
        "code": '''#!/usr/bin/env python3
"""Count log levels in <<file>> and show the first errors."""

import re
import sys
from collections import Counter

LEVEL = re.compile(r"\\b(DEBUG|INFO|WARNING|ERROR|CRITICAL)\\b")


def analyse(path):
    counts = Counter()
    errors = []
    with open(path, encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            match = LEVEL.search(line)
            if not match:
                continue
            level = match.group(1)
            counts[level] += 1
            if level in {"ERROR", "CRITICAL"} and len(errors) < 5:
                errors.append(line.rstrip())
    return counts, errors


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "<<file>>"
    counts, errors = analyse(path)
    for level, count in counts.most_common():
        print(f"{level:<10} {count}")
    if errors:
        print("\\nfirst errors:")
        for line in errors:
            print(" ", line[:160])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "sqlite table",
        "tags": ["python", "script", "sqlite", "database"],
        "desc": "store records in a SQLite database in <<db>>",
        "params": [{"db": "notes.db"}, {"db": "tasks.db"}, {"db": "scores.db"}],
        "code": '''#!/usr/bin/env python3
"""Create a SQLite table in <<db>>, insert rows and query them back."""

import sqlite3

DB = "<<db>>"


def connect():
    connection = sqlite3.connect(DB)
    connection.row_factory = sqlite3.Row
    connection.execute(
        "CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, body TEXT, done INTEGER)"
    )
    return connection


def main():
    with connect() as connection:
        connection.execute(
            "INSERT INTO notes (body, done) VALUES (?, ?)", ("buy milk", 0)
        )
        rows = connection.execute("SELECT id, body, done FROM notes ORDER BY id").fetchall()
    for row in rows:
        print(dict(row))
    print(f"{len(rows)} rows in {DB}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "retry with backoff",
        "tags": ["python", "script", "network", "robustness"],
        "desc": "retry a failing function <<tries>> times with a delay",
        "params": [{"tries": "3"}, {"tries": "5"}],
        "code": '''#!/usr/bin/env python3
"""Retry a function <<tries>> times, waiting longer after each failure."""

import random
import time


def retry(func, tries=<<tries>>, base=0.5):
    for attempt in range(1, tries + 1):
        try:
            return func()
        except Exception as error:
            if attempt == tries:
                raise
            wait = base * 2 ** (attempt - 1) + random.uniform(0, 0.2)
            print(f"attempt {attempt} failed ({error}); retrying in {wait:.1f}s")
            time.sleep(wait)


def fetch():
    raise ConnectionError("server busy")


if __name__ == "__main__":
    try:
        retry(fetch)
    except ConnectionError as error:
        print("gave up:", error)''',
    },
    {
        "name": "environment variables",
        "tags": ["python", "script", "config", "environment"],
        "desc": "read <<var>> from an environment variable with a default",
        "params": [{"var": "API_KEY"}, {"var": "DATABASE_URL"}, {"var": "PORT"}],
        "code": '''#!/usr/bin/env python3
"""Read settings from the environment instead of hard-coding them."""

import os


def required(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(f"{name} is not set")
    return value


def main():
    token = required("<<var>>")
    timeout = float(os.environ.get("TIMEOUT", "15"))
    debug = os.environ.get("DEBUG", "0") == "1"
    print(f"<<var>> loaded ({len(token)} characters, timeout {timeout:g}s, debug={debug})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "chunk a list",
        "tags": ["python", "script", "lists", "utility"],
        "desc": "split a list into chunks of <<size>>",
        "params": [{"size": "100"}, {"size": "10"}, {"size": "1000"}],
        "code": '''#!/usr/bin/env python3
"""Split a list into batches of <<size>> items."""

from itertools import islice


def chunked(items, size=<<size>>):
    iterator = iter(items)
    while batch := list(islice(iterator, size)):
        yield batch


def main():
    numbers = list(range(1, 26))
    for index, batch in enumerate(chunked(numbers), start=1):
        print(f"batch {index}: {batch[0]}..{batch[-1]} ({len(batch)} items)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "parse arguments",
        "tags": ["python", "script", "cli", "argparse"],
        "desc": "build a command line tool that takes a <<topic>> argument",
        "params": [{"topic": "folder"}, {"topic": "file"}],
        "code": '''#!/usr/bin/env python3
"""A command line tool with subcommands and sensible defaults."""

import argparse
from pathlib import Path


def run(target, verbose):
    if not target.exists():
        print(f"{target} does not exist")
        return 1
    if verbose:
        print(f"working on {target.resolve()}")
    print(f"processed {target}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Process a <<topic>>")
    parser.add_argument("target", type=Path, nargs="?", default=Path("."))
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        print(f"would process {args.target}")
        return 0
    return run(args.target, args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "send an email",
        "tags": ["python", "script", "email", "smtplib"],
        "desc": "send an email to <<recipient>> when a job fails",
        "params": [{"recipient": "you@example.com"}, {"recipient": "team@example.com"}],
        "code": '''#!/usr/bin/env python3
"""Email <<recipient>> with smtplib — no extra packages needed."""

import smtplib
from email.message import EmailMessage

SMTP_HOST = "smtp.example.com"
SMTP_PORT = 587
SENDER = "bot@example.com"
PASSWORD = "use-an-app-password"
RECIPIENT = "<<recipient>>"


def send(subject, body):
    message = EmailMessage()
    message["From"] = SENDER
    message["To"] = RECIPIENT
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as smtp:
        smtp.starttls()
        smtp.login(SENDER, PASSWORD)
        smtp.send_message(message)


def main():
    send("job failed", "The nightly import raised an error. Check the logs.")
    print("sent to", RECIPIENT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "check a website is up",
        "tags": ["python", "script", "network", "monitoring"],
        "desc": "check that <<url>> is up and how fast it answers",
        "params": [{"url": "https://example.com"}, {"url": "https://www.python.org"}],
        "code": '''#!/usr/bin/env python3
"""Check that <<url>> answers, and how long it took."""

import time
import urllib.error
import urllib.request

URL = "<<url>>"


def check(url, timeout=10):
    request = urllib.request.Request(url, headers={"User-Agent": "onyx-check/1.0"})
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read(1024)
            return response.status, time.perf_counter() - started
    except urllib.error.HTTPError as error:
        return error.code, time.perf_counter() - started
    except urllib.error.URLError as error:
        return None, str(error.reason)


def main():
    status, elapsed = check(URL)
    if status is None:
        print(f"{URL} unreachable: {elapsed}")
        return 2
    print(f"{URL} -> {status} in {elapsed:.2f}s")
    return 0 if status < 400 else 1


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "resize images",
        "tags": ["python", "script", "images", "pillow"],
        "desc": "resize every image in a folder to <<size>> pixel thumbnails",
        "params": [{"size": "300"}, {"size": "800"}],
        "code": '''#!/usr/bin/env python3
"""Shrink every image in a folder to <<size>>px thumbnails.

Needs Pillow: python -m pip install Pillow
"""

import sys
from pathlib import Path

from PIL import Image

MAX_SIZE = <<size>>
SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def resize(source, target):
    target.mkdir(exist_ok=True)
    count = 0
    for path in sorted(source.iterdir()):
        if path.suffix.lower() not in SUFFIXES:
            continue
        with Image.open(path) as image:
            image.thumbnail((MAX_SIZE, MAX_SIZE))
            image.save(target / f"{path.stem}-{MAX_SIZE}{path.suffix.lower()}")
        count += 1
    return count


def main():
    source = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    print(f"{resize(source, source / 'thumbs')} images resized to <<size>>px")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "scrape links",
        "tags": ["python", "script", "network", "html"],
        "desc": "list every link on the page <<url>>",
        "params": [{"url": "https://example.com"}, {"url": "https://www.python.org"}],
        "code": '''#!/usr/bin/env python3
"""List the links on <<url>> with the standard library."""

import sys
import urllib.request
from html.parser import HTMLParser

URL = "<<url>>"


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href and href.startswith(("http://", "https://")):
            self.links.append(href)


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else URL
    request = urllib.request.Request(url, headers={"User-Agent": "onyx-script/1.0"})
    with urllib.request.urlopen(request, timeout=15) as response:
        page = response.read().decode("utf-8", errors="replace")
    parser = Links()
    parser.feed(page)
    for link in dict.fromkeys(parser.links):
        print(link)
    print(f"\\n{len(parser.links)} links")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "html report",
        "tags": ["python", "script", "html", "report"],
        "desc": "build an HTML report called <<title>> from a list of rows",
        "params": [{"title": "Weekly scores"}, {"title": "Build summary"}],
        "code": '''#!/usr/bin/env python3
"""Build the HTML report <<title>> from a list of rows."""

from pathlib import Path

ROWS = [("Ada", 91), ("Alan", 88), ("Grace", 95)]


def report(rows, title="<<title>>"):
    body = "\\n".join(
        f"    <tr><td>{name}</td><td>{score}</td></tr>" for name, score in rows
    )
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{title}</title></head>
<body>
  <h1>{title}</h1>
  <table border="1" cellpadding="4">
    <tr><th>Name</th><th>Score</th></tr>
{body}
  </table>
</body></html>
"""


def main():
    Path("report.html").write_text(report(ROWS), encoding="utf-8")
    print("wrote report.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
    {
        "name": "watch a folder",
        "tags": ["python", "script", "files", "watch"],
        "desc": "watch <<folder>> and print new files as they arrive",
        "params": [{"folder": "downloads"}, {"folder": "inbox"}],
        "code": '''#!/usr/bin/env python3
"""Watch <<folder>> and report files that appear or disappear."""

import time
from pathlib import Path

FOLDER = Path("<<folder>>")
INTERVAL = 5


def snapshot(folder):
    return {path.name for path in folder.iterdir() if path.is_file()}


def main():
    known = snapshot(FOLDER)
    print(f"watching {FOLDER} every {INTERVAL}s")
    while True:
        time.sleep(INTERVAL)
        current = snapshot(FOLDER)
        for name in sorted(current - known):
            print(f"new:  {name}")
        for name in sorted(known - current):
            print(f"gone: {name}")
        known = current


if __name__ == "__main__":
    raise SystemExit(main())''',
    },
]

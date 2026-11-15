#!/usr/bin/env python3
"""Build training/base-training.jsonl.

Sources, in priority order:
  1. training/seed.jsonl        conversation, English usage and hand-written Python Q&A
  2. training/recipes.py        complete, compile-checked scripts (several variants each)
  3. CONCEPTS below             short Python answers: idioms, errors, tooling
  4. the standard library       signatures and summaries pulled from this interpreter

The pack always lands on exactly TARGET records. Every Python block is parsed
with ast before it is written, so the pack never ships code that cannot compile.
"""

import ast
import importlib
import inspect
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "training" / "base-training.jsonl"
SEED = ROOT / "training" / "seed.jsonl"
TARGET = 10000

sys.path.insert(0, str(ROOT / "training"))
from recipes import RECIPES  # noqa: E402

# Modules worth documenting for everyday scripting. Kept in a fixed order so
# the pack is reproducible.
MODULES = [
    "itertools", "collections", "functools", "operator", "datetime", "pathlib",
    "json", "csv", "re", "glob", "shutil", "tempfile", "os", "os.path",
    "subprocess", "argparse", "logging", "sqlite3", "typing", "dataclasses",
    "enum", "contextlib", "io", "zipfile", "tarfile", "gzip", "hashlib",
    "statistics", "decimal", "fractions", "uuid", "base64", "secrets",
    "random", "math", "string", "textwrap", "pprint", "copy", "heapq",
    "bisect", "time", "calendar", "inspect", "traceback", "warnings",
    "urllib.parse", "urllib.request", "http.client", "difflib", "fnmatch",
    "threading", "queue", "concurrent.futures", "unittest",
]

BUILTIN_TYPES = ["str", "list", "dict", "set", "int", "float", "bytes"]

CONCEPTS = [
    {
        "q": ["how do i read a whole text file in one line of python",
              "python one line read file",
              "what is the shortest way to read a file in python"],
        "a": "`Path('notes.txt').read_text(encoding='utf-8')` — with `from pathlib import Path`. "
             "For binary data use `.read_bytes()`. Write with `.write_text(text, encoding='utf-8')`. "
             "Always pass `encoding`; the default depends on the platform, which is how files end up mangled on Windows.",
        "tags": ["python", "files", "pathlib", "idioms"],
    },
    {
        "q": ["how do i read a file line by line in python",
              "python loop over the lines of a file",
              "read a large file without loading it into memory"],
        "a": "Iterate over the handle — it yields one line at a time and streams:\n\n```python\nwith open('app.log', encoding='utf-8') as f:\n    for line in f:\n        print(line.rstrip())\n```\n\n"
             "Avoid `f.readlines()` on a big file: it builds the whole list in memory. `for number, line in enumerate(f, start=1)` gives you line numbers for free.",
        "tags": ["python", "files", "loops", "streaming"],
    },
    {
        "q": ["how do i write to a file in python",
              "python save text to a file",
              "create a file and write lines in python"],
        "a": "```python\nwith open('out.txt', 'w', encoding='utf-8') as f:\n    f.write('hello\\n')\n    f.writelines(['one\\n', 'two\\n'])\n```\n\n"
             "`'w'` truncates the file, `'a'` appends, `'x'` fails if it exists. The `with` block closes the file even if the body raises — skipping it is the usual cause of half-written files.",
        "tags": ["python", "files", "write", "basics"],
    },
    {
        "q": ["how do i handle a missing file in python",
              "python file not found error",
              "check if a file exists before opening it python"],
        "a": "Catch the error instead of checking first — checking is a race:\n\n```python\nfrom pathlib import Path\n\ntry:\n    text = Path('notes.txt').read_text(encoding='utf-8')\nexcept FileNotFoundError:\n    text = ''\n```\n\n"
             "`FileNotFoundError` is a subclass of `OSError`, so `except OSError` also covers permission and disk errors. `Path.exists()` is fine for display, not for guarding an open.",
        "tags": ["python", "files", "errors", "exceptions"],
    },
    {
        "q": ["how do i catch several exceptions in python",
              "python except multiple errors",
              "what is the order of except blocks in python"],
        "a": "```python\ntry:\n    number = int(raw)\nexcept (TypeError, ValueError) as error:\n    print('bad input:', error)\nexcept OSError:\n    raise\n```\n\n"
             "Name several types in one tuple, and order specific before general. A bare `except:` also catches KeyboardInterrupt and SystemExit — use `except Exception:` if you really mean everything.",
        "tags": ["python", "exceptions", "errors", "basics"],
    },
    {
        "q": ["what does a keyerror mean in python",
              "python keyerror dict",
              "why do i get keyerror when reading a dictionary"],
        "a": "The key is not in the dict. Fix it with `d.get(key, default)` or `d.setdefault(key, [])`, or check `if key in d`.\n\n"
             "If the dict came from JSON, print `list(d.keys())` first: the shape is often nested one level deeper than expected (`data['items']` rather than `data`).",
        "tags": ["python", "dict", "errors", "keyerror"],
    },
    {
        "q": ["what is a typeerror in python",
              "python unsupported operand type",
              "why does python say unsupported operand type"],
        "a": "You used an operation on a type that does not support it — usually a string where a number belongs: `'3' + 4`. Convert explicitly with `int(...)` or `float(...)`.\n\n"
             "`int('3.5')` also raises ValueError; use `int(float('3.5'))`. Watch for `None` from functions that return nothing, which produces `'NoneType' object is not ...`.",
        "tags": ["python", "errors", "typeerror", "types"],
    },
    {
        "q": ["what does indexerror list index out of range mean",
              "python indexerror",
              "why is my list index out of range"],
        "a": "You asked for a position the list does not have — usually an off-by-one at the end. Valid indexes run from `0` to `len(items) - 1`, and negative indexes count from the end.\n\n"
             "Guard with `if items:` before `items[0]`, and use `enumerate` rather than manual counters. Empty results from a filter are the other common cause.",
        "tags": ["python", "lists", "errors", "indexerror"],
    },
    {
        "q": ["what is an attributeerror in python",
              "python object has no attribute",
              "why does python say none type has no attribute"],
        "a": "The object is not what you think it is. `'NoneType' object has no attribute 'strip'` means a function returned None, so check its return value before calling methods on it.\n\n"
             "Use `print(type(value), value)` at the failing line; `vars(obj)` or `dir(obj)` shows what the object actually offers.",
        "tags": ["python", "errors", "attributeerror", "debugging"],
    },
    {
        "q": ["what is a valueerror in python",
              "python invalid literal for int",
              "why does int fail in python"],
        "a": "The type is right but the value is not — `int('abc')`, `float('')`, `int('3.5')`. Strip whitespace first (`raw.strip()`), and wrap conversions in try/except when the input is human.\n\n"
             "`'1,234'` also fails: remove separators with `.replace(',', '')` before converting.",
        "tags": ["python", "errors", "valueerror", "numbers"],
    },
    {
        "q": ["what does indentationerror mean in python",
              "python unexpected indent",
              "why is python complaining about indentation"],
        "a": "Python uses indentation as syntax: every line in a block needs the same indentation, and a block starts after a line ending in `:`. Mixing tabs and spaces in one file produces `TabError`.\n\n"
             "Fix it by reindenting the file with four spaces; most editors have a 'convert indentation to spaces' command.",
        "tags": ["python", "errors", "indentation", "basics"],
    },
    {
        "q": ["how do i install a package in python",
              "python pip install",
              "how do i add a library to my python project"],
        "a": "In a virtual environment:\n\n```\npython -m venv .venv\nsource .venv/bin/activate        # Windows: .venv\\Scripts\\activate\npython -m pip install requests\npython -m pip freeze > requirements.txt\n```\n\n"
             "Use `python -m pip` so the install lands in the interpreter you are actually running. `pip install --user` is a fallback when you cannot create an environment.",
        "tags": ["python", "pip", "venv", "setup"],
    },
    {
        "q": ["how do i create a virtual environment in python",
              "python venv",
              "why do i need a virtual environment"],
        "a": "```\npython -m venv .venv\nsource .venv/bin/activate\npython -c \"import sys; print(sys.prefix)\"\n```\n\n"
             "It gives the project its own packages, so upgrading one project cannot break another. Commit nothing from `.venv`; commit `requirements.txt` (or `pyproject.toml`) instead.",
        "tags": ["python", "venv", "setup", "pip"],
    },
    {
        "q": ["how do i check which python version is running",
              "python version command",
              "which interpreter is my script using"],
        "a": "```\nimport sys\nprint(sys.version)\nprint(sys.executable)\n```\n\n"
             "`sys.executable` matters more than the version: it shows which interpreter runs, which is how you catch a script using system Python instead of your virtual environment. Inside a script, `sys.version_info >= (3, 11)` is the portable check.",
        "tags": ["python", "version", "interpreter", "debugging"],
    },
    {
        "q": ["what is if __name__ == __main__ in python",
              "python main guard",
              "why do python files have if name equals main"],
        "a": "It runs the block only when the file is executed directly, not when it is imported. That keeps a module importable without side effects:\n\n```python\ndef main():\n    ...\n\nif __name__ == '__main__':\n    raise SystemExit(main())\n```\n\n"
             "`raise SystemExit(main())` turns the return value into the process exit code, which is what shells and CI read.",
        "tags": ["python", "main", "modules", "basics"],
    },
    {
        "q": ["how do i import a module from another folder in python",
              "python import from parent directory",
              "python module not found error"],
        "a": "Put the code in a package (a folder with `__init__.py`) and run Python from the project root: `python -m package.script`.\n\n"
             "`ModuleNotFoundError` usually means the working directory is wrong, not that the file is missing — check with `python -c \"import sys; print(sys.path)\"`. Avoid `sys.path.append` hacks; they break as soon as the script is run from elsewhere.",
        "tags": ["python", "imports", "modules", "packaging"],
    },
    {
        "q": ["how do i make a command line tool in python",
              "python argparse example",
              "how do i parse command line arguments in python"],
        "a": "```python\nimport argparse\nfrom pathlib import Path\n\nparser = argparse.ArgumentParser(description='Count words')\nparser.add_argument('path', type=Path)\nparser.add_argument('-n', '--top', type=int, default=10)\nparser.add_argument('--dry-run', action='store_true')\nargs = parser.parse_args()\nprint(args.path, args.top, args.dry_run)\n```\n\n"
             "Use `type=Path` for paths and `action='store_true'` for flags. `argparse` prints help and exits on bad input for you, so never hand-roll `sys.argv` parsing.",
        "tags": ["python", "argparse", "cli", "script"],
    },
    {
        "q": ["how do i print with two decimal places in python",
              "python format float round to 2 decimals",
              "python f string decimal places"],
        "a": "`f'{value:.2f}'` for display, `round(value, 2)` for a number. Thousands separators: `f'{value:,.2f}'`.\n\n"
             "`round()` uses banker's rounding (`round(2.5)` is 2), and floats cannot represent most decimals exactly — use `decimal.Decimal` for money and never compare floats with `==`.",
        "tags": ["python", "formatting", "numbers", "f-strings"],
    },
    {
        "q": ["how do i join a list of strings in python",
              "python list to string",
              "how do i concatenate strings in a list"],
        "a": "`', '.join(items)` — the separator is the string you call it on. Every item must be a string, so convert first: `', '.join(str(n) for n in numbers)`.\n\n"
             "Do not build long strings with `+=` in a loop; collect the parts in a list and `''.join(parts)` once. For lines, `'\\n'.join(lines)` is the one-liner.",
        "tags": ["python", "strings", "join", "lists"],
    },
    {
        "q": ["how do i split a string in python",
              "python string to list",
              "how do i split on a comma or whitespace"],
        "a": "`text.split()` splits on any whitespace and drops empty pieces; `text.split(',')` splits on a literal separator; `text.split(',', 2)` limits the number of splits.\n\n"
             "`'a,b,'.split(',')` gives `['a', 'b', '']` — filter empties with `[part for part in text.split(',') if part.strip()]`. For CSV with quotes, use the `csv` module instead of `split`.",
        "tags": ["python", "strings", "split", "csv"],
    },
    {
        "q": ["how do i check if a string contains something in python",
              "python substring check",
              "how do i find text inside a string"],
        "a": "`'error' in line` for a yes/no test; `line.find('error')` or `line.index('error')` for a position (-1 versus ValueError when absent).\n\n"
             "Case-insensitive: `'error' in line.lower()`. For patterns, `re.search(r'err(or)?', line)` — remember `re.search` finds anywhere while `re.match` only anchors at the start.",
        "tags": ["python", "strings", "search", "regex"],
    },
    {
        "q": ["how do i remove whitespace from a string in python",
              "python strip whitespace",
              "how do i trim a string"],
        "a": "`.strip()` removes leading and trailing whitespace, `.lstrip()`/`.rstrip()` one side, `.strip('\"')` a specific set of characters. Inside the string, `' '.join(text.split())` collapses runs of spaces.\n\n"
             "Non-breaking spaces (`\\xa0`) survive `.strip()` in old code; in Python 3 they are whitespace and are removed.",
        "tags": ["python", "strings", "strip", "text"],
    },
    {
        "q": ["how do i replace text in a string in python",
              "python string replace",
              "how do i swap a word in a string"],
        "a": "`text.replace('old', 'new')` replaces every occurrence and returns a new string; pass a count to limit it: `text.replace('a', 'b', 1)`.\n\n"
             "Strings are immutable, so reassign the result. For case-insensitive replacement use `re.sub(r'\\bold\\b', 'new', text, flags=re.IGNORECASE)`.",
        "tags": ["python", "strings", "replace", "regex"],
    },
    {
        "q": ["how do i sort a list of dictionaries in python",
              "python sort dicts by key",
              "how do i sort a list by a field"],
        "a": "```python\nrows.sort(key=lambda row: row['age'])                 # ascending\nrows.sort(key=lambda row: (-row['age'], row['name'])) # age desc, then name\nsorted(rows, key=lambda row: row.get('age', 0))\n```\n\n"
             "`.sort()` changes the list and returns None; `sorted()` returns a new list. Mixed types raise TypeError: normalise with `str(...)` in the key if the field is sometimes a number and sometimes text.",
        "tags": ["python", "sorting", "dict", "lists"],
    },
    {
        "q": ["how do i find the max or min in a list of dictionaries",
              "python max by key",
              "python min of a list of tuples"],
        "a": "`max(rows, key=lambda row: row['score'])` and `min(...)` the same way. To get the index instead, use `max(range(len(items)), key=items.__getitem__)` or better `max(enumerate(items), key=lambda pair: pair[1])[0]`.\n\n"
             "On an empty sequence both raise ValueError; pass `default=` (Python 3.4+) when empty is normal.",
        "tags": ["python", "lists", "max", "min"],
    },
    {
        "q": ["how do i merge two dictionaries in python",
              "python combine dicts",
              "python dict update with another dict"],
        "a": "`merged = a | b` (3.9+) keeps b's values on conflicts; earlier versions use `{**a, **b}` or `a.copy()` then `.update(b)`.\n\n"
             "To merge deeply (nested dicts surviving), write a small recursive function or use `collections.ChainMap` for lookup-only merging.",
        "tags": ["python", "dict", "merge", "basics"],
    },
    {
        "q": ["how do i count occurrences in a list in python",
              "python count items in a list",
              "python frequency count"],
        "a": "`collections.Counter(items)` is the tool: `counts['a']`, `counts.most_common(5)`, `sum(counts.values())`.\n\n"
             "Counter also does arithmetic (`c1 + c2`) and works on any hashable iterable, including characters of a string. For a single value, `items.count(x)` is fine but O(n) per call.",
        "tags": ["python", "counter", "collections", "count"],
    },
    {
        "q": ["how do i get unique values from a list in python",
              "python remove duplicates from a list keeping order",
              "python list to set"],
        "a": "`list(dict.fromkeys(items))` keeps the original order; `list(set(items))` is faster but unordered. For a set of tuples or dicts, keep a `seen` set and build the output list.\n\n"
             "Unhashable items (lists, dicts) need a key: `seen.add(tuple(row))` or a tuple of the fields you care about.",
        "tags": ["python", "sets", "dedupe", "lists"],
    },
    {
        "q": ["how do i check if a key exists in a dict in python",
              "python dict has key",
              "python checking dictionary membership"],
        "a": "`if key in d:` is the right test. `d[key]` raises KeyError, `d.get(key)` returns None, `d.get(key, default)` returns your default.\n\n"
             "To read-and-create, `d.setdefault(key, []).append(value)` avoids a double lookup. In Python 3.8+, `d.keys()`/`d.items()` are live views, not copies.",
        "tags": ["python", "dict", "membership", "basics"],
    },
    {
        "q": ["how do i iterate over a dictionary in python",
              "python loop through dict keys and values",
              "python dict items"],
        "a": "`for key, value in d.items():` — and `d.keys()`/`d.values()` when you need one side. Sorting: `for key in sorted(d):`.\n\n"
             "Do not add or delete keys while iterating: collect the changes and apply them after, or iterate over `list(d.items())`.",
        "tags": ["python", "dict", "loops", "basics"],
    },
    {
        "q": ["how do i read a csv file in python",
              "python csv reader",
              "how do i parse csv without pandas"],
        "a": "```python\nimport csv\n\nwith open('data.csv', newline='', encoding='utf-8') as f:\n    for row in csv.DictReader(f):\n        print(row['name'], row['amount'])\n```\n\n"
             "`newline=''` stops Windows line endings from producing blank rows. Values arrive as strings — convert with `float(row['amount'])` and handle bad cells. `csv.writer` with `lineterminator='\\n'` writes clean files.",
        "tags": ["python", "csv", "files", "data"],
    },
    {
        "q": ["how do i write a csv file in python",
              "python csv writer",
              "python write rows to csv"],
        "a": "```python\nimport csv\n\nrows = [{'name': 'Ada', 'score': 91}, {'name': 'Alan', 'score': 88}]\nwith open('out.csv', 'w', newline='', encoding='utf-8') as f:\n    writer = csv.DictWriter(f, fieldnames=['name', 'score'])\n    writer.writeheader()\n    writer.writerows(rows)\n```\n\n"
             "`fieldnames` must cover every key or `extrasaction='ignore'` is needed. Use `quoting=csv.QUOTE_MINIMAL` (the default) unless an export tool demands otherwise.",
        "tags": ["python", "csv", "write", "data"],
    },
    {
        "q": ["how do i read json in python",
              "python json load",
              "python parse json file"],
        "a": "`json.loads(text)` for a string, `json.load(handle)` for a file, and `json.loads(Path('x.json').read_text())` for the one-liner.\n\n"
             "Bad JSON raises `json.JSONDecodeError` with the line and column — print the offending slice rather than the whole document. JSON keys are always strings, and `true/false/null` become `True/False/None`.",
        "tags": ["python", "json", "files", "data"],
    },
    {
        "q": ["how do i write json in python",
              "python json dump",
              "python save a dict as json"],
        "a": "```python\nimport json\nfrom pathlib import Path\n\nPath('out.json').write_text(\n    json.dumps(data, indent=2, ensure_ascii=False, sort_keys=True),\n    encoding='utf-8',\n)\n```\n\n"
             "`indent=2` makes it readable and diffable. Objects that are not JSON-native (dates, sets, Paths) need `default=str` or a custom encoder, otherwise you get `TypeError: Object of type ... is not JSON serializable`.",
        "tags": ["python", "json", "write", "data"],
    },
    {
        "q": ["how do i use regular expressions in python",
              "python re search match findall",
              "python regex example"],
        "a": "```python\nimport re\n\nre.search(r'\\d{4}-\\d{2}-\\d{2}', text)   # anywhere, None if absent\nre.match(r'^ID', text)                  # only at the start\nre.findall(r'\\w+@\\w+\\.\\w+', text)      # list of matches\nre.sub(r'\\s+', ' ', text).strip()       # collapse whitespace\n```\n\n"
             "Compile hot patterns once with `pattern = re.compile(...)` and reuse `pattern.search(...)`. Group captures with `match.group(1)`. Use raw strings (`r'...'`) so backslashes survive.",
        "tags": ["python", "regex", "re", "text"],
    },
    {
        "q": ["how do i use a date in python",
              "python datetime today format",
              "python format a date as a string"],
        "a": "```python\nfrom datetime import datetime, timedelta\n\nnow = datetime.now()\nstamp = now.strftime('%Y-%m-%d %H:%M:%S')\nweek_ago = now - timedelta(days=7)\nparsed = datetime.strptime('2026-11-15', '%Y-%m-%d')\n```\n\n"
             "Use `isoformat()` for storage, `strftime` for display, `strptime` to parse. `datetime.now()` is naive local time; `datetime.now(timezone.utc)` is aware and what timestamps should be.",
        "tags": ["python", "datetime", "dates", "formatting"],
    },
    {
        "q": ["how do i measure how long code takes in python",
              "python time a function",
              "python timer elapsed"],
        "a": "```python\nimport time\n\nstart = time.perf_counter()\nwork()\nprint(f'{time.perf_counter() - start:.3f}s')\n```\n\n"
             "`perf_counter()` is the high-resolution clock meant for timing; `time.time()` can jump with clock changes. Repeat a few times and take the best run — one measurement is mostly noise.",
        "tags": ["python", "timing", "performance", "time"],
    },
    {
        "q": ["how do i run a shell command in python",
              "python subprocess run",
              "python execute a command and read output"],
        "a": "```python\nimport subprocess\n\nresult = subprocess.run(\n    ['ls', '-la'], capture_output=True, text=True, check=True\n)\nprint(result.stdout)\n```\n\n"
             "Pass a list, never a string with `shell=True` and user input. `check=True` raises CalledProcessError on a non-zero exit; `text=True` decodes output as str. `subprocess.run` is the modern replacement for `os.system`.",
        "tags": ["python", "subprocess", "shell", "script"],
    },
    {
        "q": ["how do i use a temporary file in python",
              "python tempfile example",
              "python create a temp directory"],
        "a": "```python\nimport tempfile\nfrom pathlib import Path\n\nwith tempfile.TemporaryDirectory() as folder:\n    path = Path(folder) / 'work.txt'\n    path.write_text('hello')\n    print(path.read_text())\n# folder and its contents are gone here\n```\n\n"
             "`NamedTemporaryFile(delete=False)` is for tools that need a real path after closing. Temp files are created in the system temp dir, so never assume they are on the same filesystem as your data.",
        "tags": ["python", "tempfile", "files", "script"],
    },
    {
        "q": ["how do i log instead of print in python",
              "python logging setup",
              "python write logs to a file and the console"],
        "a": "```python\nimport logging\n\nlogging.basicConfig(\n    level=logging.INFO,\n    format='%(asctime)s %(levelname)s %(message)s',\n    handlers=[logging.FileHandler('app.log'), logging.StreamHandler()],\n)\nlogging.info('started')\n```\n\n"
             "Levels run DEBUG < INFO < WARNING < ERROR < CRITICAL. Use `logging.exception()` inside an `except` block to include the traceback. Libraries should call `logging.getLogger(__name__)`, not `basicConfig`.",
        "tags": ["python", "logging", "script", "debugging"],
    },
    {
        "q": ["how do i test my python code",
              "python unittest example",
              "how do i write a unit test in python"],
        "a": "```python\nimport unittest\n\n\ndef add(a, b):\n    return a + b\n\n\nclass TestAdd(unittest.TestCase):\n    def test_adds(self):\n        self.assertEqual(add(2, 3), 5)\n\n    def test_negative(self):\n        self.assertEqual(add(-1, 1), 0)\n\n\nif __name__ == '__main__':\n    unittest.main()\n```\n\n"
             "Run with `python -m unittest` or `python -m pytest` (pytest also runs unittest files). Test the behaviour you promise, including one failure case per function.",
        "tags": ["python", "tests", "unittest", "quality"],
    },
    {
        "q": ["how do i structure a python project",
              "python project layout",
              "where should i put my python files"],
        "a": "```\nproject/\n  pyproject.toml\n  README.md\n  src/app/__init__.py\n  src/app/cli.py\n  tests/test_cli.py\n```\n\n"
             "Keep code under `src/`, tests beside it, and run modules with `python -m app.cli` from the project root. Configuration lives in `pyproject.toml`; a `requirements.txt` is enough for scripts.",
        "tags": ["python", "project", "structure", "packaging"],
    },
    {
        "q": ["how do i type hints work in python",
              "python type annotations",
              "how do i annotate function arguments in python"],
        "a": "```python\ndef greet(name: str, times: int = 1) -> str:\n    return f'Hello, {name}!' * times\n\nnumbers: list[int] = [1, 2, 3]\nlookup: dict[str, float] = {}\n```\n\n"
             "Annotations are documentation plus what type checkers read — Python does not enforce them at runtime. Built-in generics (`list[int]`) work in 3.9+; use `from __future__ import annotations` for older code. Check with `mypy` or `pyright`.",
        "tags": ["python", "typing", "annotations", "quality"],
    },
    {
        "q": ["what is a decorator in python",
              "python decorator example",
              "how do i write my own decorator"],
        "a": "```python\nimport functools\n\n\ndef logged(func):\n    @functools.wraps(func)\n    def wrapper(*args, **kwargs):\n        print('calling', func.__name__)\n        return func(*args, **kwargs)\n    return wrapper\n\n\n@logged\ndef add(a, b):\n    return a + b\n```\n\n"
             "A decorator takes a function and returns a replacement. `functools.wraps` keeps the name and docstring. Decorators with arguments need one more layer.",
        "tags": ["python", "decorators", "functions", "idioms"],
    },
    {
        "q": ["what is a context manager in python",
              "python with statement class",
              "how do i write __enter__ and __exit__"],
        "a": "```python\nclass Timer:\n    def __enter__(self):\n        self.start = time.perf_counter()\n        return self\n\n    def __exit__(self, *exc):\n        print(f'{time.perf_counter() - self.start:.3f}s')\n        return False\n```\n\n"
             "Or use `@contextlib.contextmanager` on a generator that yields once. `with` guarantees cleanup runs even when the body raises, which is why files and locks use it.",
        "tags": ["python", "context-manager", "classes", "idioms"],
    },
    {
        "q": ["what is a generator in python",
              "python yield explained",
              "difference between list and generator"],
        "a": "A generator produces values lazily, one at a time, so it can stream data larger than memory:\n\n```python\ndef read_lines(path):\n    with open(path, encoding='utf-8') as f:\n        for line in f:\n            yield line.rstrip()\n```\n\n"
             "It runs until the first `yield`, then pauses. Use a generator expression `(x * 2 for x in items)` when you only iterate once; a list when you need indexing, len, or several passes.",
        "tags": ["python", "generators", "yield", "performance"],
    },
    {
        "q": ["what is the difference between a list and a tuple in python",
              "python list vs tuple",
              "when should i use a tuple"],
        "a": "Lists are mutable and for collections that change; tuples are immutable, hashable and lighter, for fixed records like `(x, y)` or dict keys.\n\n"
             "Immutability is the point: a tuple can be a dict key or a set member, and it signals 'this group does not change'. Named tuples or dataclasses are better when the fields need names.",
        "tags": ["python", "lists", "tuples", "types"],
    },
    {
        "q": ["what is the difference between == and is in python",
              "python identity versus equality",
              "why does is comparison fail in python"],
        "a": "`==` compares values, `is` compares identity (the same object). Use `==` for numbers, strings and containers, and `is` only with `None`, `True`, `False`.\n\n"
             "`a is b` can be True for small ints and short strings because of interning — which is exactly why it is an unreliable test for equality.",
        "tags": ["python", "comparison", "identity", "basics"],
    },
    {
        "q": ["what is the difference between a shallow and a deep copy in python",
              "python copy deepcopy",
              "why does changing a list change my original"],
        "a": "`b = a` copies the reference; `b = a.copy()` (or `list(a)`, `dict(a)`) is shallow — nested objects are shared; `copy.deepcopy(a)` copies everything.\n\n"
             "The classic bug is a mutable default: `def f(items=[])` keeps one list across calls. Use `def f(items=None)` and create the list inside.",
        "tags": ["python", "copy", "mutability", "bugs"],
    },
    {
        "q": ["why is my mutable default argument in python broken",
              "python default argument list shared",
              "python function default value gotcha"],
        "a": "Default values are evaluated once, when the function is defined, so a list default is shared by every call:\n\n```python\ndef add(item, items=None):\n    if items is None:\n        items = []\n    items.append(item)\n    return items\n```\n\n"
             "This applies to lists, dicts and sets. Immutable defaults like `0`, `''` and `None` are safe, apart from `datetime.now()` which is also frozen at import time.",
        "tags": ["python", "functions", "defaults", "bugs"],
    },
    {
        "q": ["how do i check if a variable is a number or a string in python",
              "python isinstance example",
              "python type checking at runtime"],
        "a": "`isinstance(value, (int, float))` — it also accepts subclasses, which `type(value) is int` does not. `bool` is a subclass of `int`, so exclude it explicitly when it matters.\n\n"
             "For strings: `isinstance(value, str)`. For duck typing, test what you need instead: `hasattr(value, 'read')`.",
        "tags": ["python", "types", "isinstance", "validation"],
    },
    {
        "q": ["how do i convert a string to a number in python",
              "python string to int float",
              "python parse a number from text"],
        "a": "`int('42')`, `float('4.2')`, and for messy input `float(raw.strip().replace(',', ''))` inside a try/except.\n\n"
             "`int()` truncates strings with decimals only via `int(float(text))`. For currency use `decimal.Decimal(text)`; for bases use `int('ff', 16)`.",
        "tags": ["python", "conversion", "numbers", "strings"],
    },
    {
        "q": ["how do i round numbers in python",
              "python round half up",
              "python math ceil floor"],
        "a": "`round(x)` and `round(x, 2)` round to nearest (ties to even); `math.floor`, `math.ceil` and `math.trunc` go down, up and toward zero.\n\n"
             "For display, formatting is clearer than rounding: `f'{x:.2f}'`. For money, `Decimal(...).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)`.",
        "tags": ["python", "numbers", "rounding", "math"],
    },
    {
        "q": ["how do i generate a random number in python",
              "python random int choice",
              "python pick a random item"],
        "a": "`random.randint(1, 6)` (inclusive), `random.choice(items)`, `random.sample(items, 3)` (no repeats), `random.shuffle(items)` in place.\n\n"
             "`random` is fine for games and sampling, never for passwords or tokens — use `secrets.token_urlsafe()` or `secrets.choice` there. Seed with `random.seed(42)` for reproducible tests.",
        "tags": ["python", "random", "numbers", "secrets"],
    },
    {
        "q": ["how do i get the file name and extension from a path in python",
              "python pathlib stem suffix",
              "python split path into name and extension"],
        "a": "```python\nfrom pathlib import Path\n\npath = Path('/data/report.final.csv')\npath.name        # 'report.final.csv'\npath.stem        # 'report.final'\npath.suffix      # '.csv'\npath.parent      # '/data'\npath.with_suffix('.json')\n```\n\n"
             "`suffixes` returns all of them. `os.path.splitext` is the older equivalent. Never build paths with string concatenation — `Path / 'name'` handles separators.",
        "tags": ["python", "pathlib", "paths", "files"],
    },
    {
        "q": ["how do i list files in a folder in python",
              "python glob directory listing",
              "python find all files in a directory"],
        "a": "```python\nfrom pathlib import Path\n\nfor path in Path('data').glob('*.csv'):\n    print(path.name)\n\nfor path in Path('.').rglob('*.py'):   # recursive\n    print(path)\n```\n\n"
             "`glob` is a direct match, `rglob` walks subfolders. Use `sorted(...)` for a stable order, and `path.is_file()` to skip directories. `os.listdir` returns bare names and is easy to misuse.",
        "tags": ["python", "pathlib", "files", "glob"],
    },
    {
        "q": ["how do i create a folder in python",
              "python make directory if not exists",
              "python mkdir parents"],
        "a": "`Path('out/data').mkdir(parents=True, exist_ok=True)` — parents creates the whole chain and exist_ok stops the FileExistsError on a rerun.\n\n"
             "Use `os.makedirs(path, exist_ok=True)` in older code. Check `is_dir()` before treating a path as a folder; a file with that name raises NotADirectoryError later.",
        "tags": ["python", "files", "pathlib", "directories"],
    },
    {
        "q": ["how do i copy or move a file in python",
              "python shutil copy move",
              "python rename a file"],
        "a": "`shutil.copy2(src, dst)` keeps metadata, `shutil.move(src, dst)` moves (and renames), `Path.rename(new)` renames within a filesystem.\n\n"
             "`copy2` fails if the target directory is missing, so `Path(dst).parent.mkdir(parents=True, exist_ok=True)` first. Copying a file onto itself raises SameFileError.",
        "tags": ["python", "shutil", "files", "copy"],
    },
    {
        "q": ["how do i check disk space or file size in python",
              "python file size bytes",
              "python disk usage"],
        "a": "`Path('x').stat().st_size` gives bytes; `shutil.disk_usage('/')` gives total, used and free.\n\n"
             "Format for humans with a small helper over `1024`, `1024**2`, `1024**3`. Directory sizes need a walk: `sum(p.stat().st_size for p in Path('.').rglob('*') if p.is_file())`.",
        "tags": ["python", "files", "size", "shutil"],
    },
    {
        "q": ["how do i hash a string in python",
              "python sha256 string",
              "python md5 checksum file"],
        "a": "```python\nimport hashlib\n\nhashlib.sha256('hello'.encode('utf-8')).hexdigest()\n\nwith open('file.bin', 'rb') as f:\n    digest = hashlib.file_digest(f, 'sha256').hexdigest()\n```\n\n"
             "Hashing needs bytes, so encode text first. `md5` and `sha1` are for checksums only, never passwords — use `hashlib.scrypt` or `bcrypt`/`argon2` for those.",
        "tags": ["python", "hashlib", "security", "files"],
    },
    {
        "q": ["how do i compare two files in python",
              "python diff two text files",
              "python filecmp example"],
        "a": "Quick check: `Path('a').read_bytes() == Path('b').read_bytes()`. For a readable diff use `difflib.unified_diff`:\n\n```python\nimport difflib\n\ndiff = difflib.unified_diff(old.splitlines(), new.splitlines(), 'old', 'new', lineterm='')\nprint('\\n'.join(diff))\n```\n\n"
             "`filecmp.cmp(a, b, shallow=False)` compares contents. Use hashes for large files instead of loading both into memory.",
        "tags": ["python", "difflib", "files", "compare"],
    },
    {
        "q": ["how do i zip or unzip files in python",
              "python zipfile create archive",
              "python extract a zip"],
        "a": "```python\nimport zipfile\n\nwith zipfile.ZipFile('out.zip', 'w', zipfile.ZIP_DEFLATED) as archive:\n    archive.write('report.csv', arcname='report.csv')\n\nwith zipfile.ZipFile('out.zip') as archive:\n    archive.extractall('exports')\n```\n\n"
             "`extractall` trusts member paths, so validate names when the archive came from someone else (zip-slip). `shutil.make_archive('out', 'zip', 'folder')` zips a whole folder in one call.",
        "tags": ["python", "zipfile", "archives", "files"],
    },
    {
        "q": ["how do i send an http request in python",
              "python urllib get request",
              "python http request without requests library"],
        "a": "```python\nimport json\nimport urllib.request\n\nrequest = urllib.request.Request(\n    'https://api.example.com/items',\n    data=json.dumps({'q': 'x'}).encode(),\n    headers={'Content-Type': 'application/json'},\n)\nwith urllib.request.urlopen(request, timeout=15) as response:\n    payload = json.load(response)\n```\n\n"
             "Always pass `timeout`; without it a stalled server hangs the script forever. `urllib.error.HTTPError` carries the status code, `URLError` covers DNS and connection failures.",
        "tags": ["python", "urllib", "network", "http"],
    },
    {
        "q": ["how do i handle a timeout in python",
              "python socket timeout",
              "python request timed out error"],
        "a": "Pass a timeout to whatever does the IO: `urlopen(url, timeout=10)`, `subprocess.run(..., timeout=30)`, or `socket.setdefaulttimeout(10)` as a blunt global.\n\n"
             "A timeout raises `TimeoutError` (or `socket.timeout`, its alias). Retry with backoff for transient timeouts, but not for 4xx responses — those will not fix themselves.",
        "tags": ["python", "timeout", "network", "errors"],
    },
    {
        "q": ["how do i print to stderr in python",
              "python error output",
              "python sys stderr print"],
        "a": "`print('problem', file=sys.stderr)`. For scripts, `raise SystemExit('problem')` prints to stderr and exits non-zero.\n\n"
             "Keep normal output on stdout so pipelines work; diagnostics go to stderr. `sys.exit(1)` is the same as `raise SystemExit(1)`.",
        "tags": ["python", "output", "stderr", "cli"],
    },
    {
        "q": ["how do i exit a python script with an error code",
              "python sys exit",
              "python return code from script"],
        "a": "`raise SystemExit(main())` at the bottom, with `main()` returning 0 on success and 1+ on failure. `sys.exit('message')` prints the message to stderr and exits 1.\n\n"
             "`SystemExit` is an exception, so `except Exception` will not swallow it. A traceback already exits with code 1, so only add explicit codes for expected failures.",
        "tags": ["python", "exit", "cli", "script"],
    },
    {
        "q": ["how do i make a python script executable on linux",
              "python shebang",
              "python chmod executable script"],
        "a": "Start the file with `#!/usr/bin/env python3`, run `chmod +x script.py`, then `./script.py` works. Keep a `.py` extension so editors and import tools still recognise it.\n\n"
             "On Windows, `.py` files are associated with the launcher (`py`), so run `py script.py`. Inside a venv, `#!/usr/bin/env python3` finds the venv interpreter only if it is on PATH — activating the venv does that.",
        "tags": ["python", "shebang", "cli", "linux"],
    },
    {
        "q": ["how do i read environment variables in python",
              "python os environ get",
              "python dotenv config"],
        "a": "`os.environ.get('API_KEY')` returns None when unset; `os.environ['API_KEY']` raises KeyError. Fail fast for required settings:\n\n```python\nkey = os.environ.get('API_KEY', '').strip()\nif not key:\n    raise SystemExit('API_KEY is not set')\n```\n\n"
             "Never commit secrets; a local `.env` file plus `python-dotenv` is the usual development setup.",
        "tags": ["python", "environment", "config", "security"],
    },
    {
        "q": ["how do i use a class in python",
              "python class example",
              "python __init__ self explained"],
        "a": "```python\nclass Account:\n    def __init__(self, owner, balance=0.0):\n        self.owner = owner\n        self.balance = balance\n\n    def deposit(self, amount):\n        if amount <= 0:\n            raise ValueError('amount must be positive')\n        self.balance += amount\n        return self.balance\n\n    def __repr__(self):\n        return f'Account({self.owner!r}, {self.balance:.2f})'\n```\n\n"
             "`self` is the instance, passed automatically. `__repr__` is for developers, `__str__` for users. Prefer dataclasses for plain data holders.",
        "tags": ["python", "classes", "oop", "basics"],
    },
    {
        "q": ["what is a dataclass in python",
              "python dataclass example",
              "how do i make a simple class for data"],
        "a": "```python\nfrom dataclasses import dataclass, field\n\n@dataclass\nclass Item:\n    name: str\n    price: float = 0.0\n    tags: list[str] = field(default_factory=list)\n```\n\n"
             "It writes `__init__`, `__repr__` and `__eq__` for you. Use `field(default_factory=list)` for mutable defaults — the plain `= []` is the shared-list bug. `frozen=True` makes it immutable and hashable.",
        "tags": ["python", "dataclasses", "classes", "idioms"],
    },
    {
        "q": ["how do i inherit from a class in python",
              "python super init",
              "python subclass example"],
        "a": "```python\nclass Animal:\n    def __init__(self, name):\n        self.name = name\n\n    def speak(self):\n        return '...'\n\n\nclass Dog(Animal):\n    def __init__(self, name, breed='mutt'):\n        super().__init__(name)\n        self.breed = breed\n\n    def speak(self):\n        return 'Woof'\n```\n\n"
             "Call `super().__init__(...)` so the parent sets its own attributes. Prefer composition over deep hierarchies; two levels is usually enough.",
        "tags": ["python", "classes", "inheritance", "oop"],
    },
    {
        "q": ["how do i make a class printable in python",
              "python __str__ __repr__",
              "python print an object nicely"],
        "a": "Define `__repr__` returning something like `Account('Ada', 10.00)` — it is what the debugger and containers show. Add `__str__` only when users see the value.\n\n"
             "Use `!r` in an f-string to call repr on a field. Without either method you get `<__main__.Account object at 0x...>`, which tells you nothing.",
        "tags": ["python", "classes", "repr", "debugging"],
    },
    {
        "q": ["how do i sort a dictionary by value in python",
              "python order dict by value",
              "python most common dict entries"],
        "a": "`sorted(d.items(), key=lambda kv: kv[1], reverse=True)` returns a list of pairs; `dict(sorted(...))` rebuilds a dict in that order.\n\n"
             "For counts, `Counter(d).most_common(5)` already does it. Dicts keep insertion order, so sorting once at the end is enough.",
        "tags": ["python", "dict", "sorting", "counter"],
    },
    {
        "q": ["how do i read numbers from input until the user stops in python",
              "python read numbers until blank line",
              "python sum user input"],
        "a": "```python\ntotal = 0\nwhile True:\n    raw = input('Number (blank to finish): ').strip()\n    if not raw:\n        break\n    try:\n        total += float(raw)\n    except ValueError:\n        print('not a number:', raw)\nprint(f'Total: {total:g}')\n```\n\n"
             "`input()` raises EOFError at end of input (piped files, Ctrl-D), so wrap long loops if the script may run non-interactively.",
        "tags": ["python", "input", "loops", "script"],
    },
    {
        "q": ["how do i make a menu in python",
              "python simple menu loop",
              "python interactive script menu"],
        "a": "```python\noptions = {'1': 'add', '2': 'list', 'q': 'quit'}\nwhile True:\n    choice = input('1) add  2) list  q) quit > ').strip().lower()\n    if choice in {'q', 'quit'}:\n        break\n    action = options.get(choice)\n    if not action:\n        print('unknown option')\n        continue\n    print(f'you chose {action}')\n```\n\n"
             "Use a dict instead of a long if/elif chain, and always offer a way out. Catch EOFError if the script might be run with piped input.",
        "tags": ["python", "cli", "input", "script"],
    },
    {
        "q": ["how do i pretty print a dictionary in python",
              "python pprint json indent",
              "python print a dict readable"],
        "a": "`from pprint import pprint; pprint(data, sort_dicts=False)` prints nested structures readably. For JSON-shaped data, `print(json.dumps(data, indent=2, default=str))` gives something you can paste.\n\n"
             "`pprint` truncates very deep structures by default; `pprint(data, depth=None)` removes that limit.",
        "tags": ["python", "pprint", "debugging", "output"],
    },
    {
        "q": ["how do i debug a python script",
              "python pdb breakpoint",
              "how do i step through python code"],
        "a": "Put `breakpoint()` where you want to stop and run normally; you drop into pdb. Commands: `n` next line, `s` step into, `c` continue, `p expr` print, `l` list source, `q` quit.\n\n"
             "For quick checks, `print(f'{value=}')` shows the expression and its value. For crashes, read the last frame of the traceback first — that is where the error actually happened.",
        "tags": ["python", "debugging", "pdb", "tools"],
    },
    {
        "q": ["how do i read a traceback in python",
              "python error traceback explained",
              "how do i find the line that failed"],
        "a": "Read from the bottom up: the last line is the exception type and message, and the frame just above it is the code that raised it. The middle frames are the call chain that got you there.\n\n"
             "`File \"x.py\", line 12, in main` is a location; `TypeError: unsupported operand type(s) for +: 'int' and 'str'` is the cause. Rerun with `python -X faulthandler` for hangs and crashes.",
        "tags": ["python", "errors", "traceback", "debugging"],
    },
    {
        "q": ["how do i suppress a warning in python",
              "python warnings filter",
              "python ignore deprecation warning"],
        "a": "`import warnings; warnings.filterwarnings('ignore', category=DeprecationWarning)` silences a class of warning; `warnings.simplefilter('once')` deduplicates.\n\n"
             "Fix the underlying cause where you can: deprecated APIs usually have a direct replacement named in the message. Silencing warnings globally hides real problems in dependencies.",
        "tags": ["python", "warnings", "deprecation", "tools"],
    },
    {
        "q": ["how do i check for null or none in python",
              "python is none check",
              "python value is missing"],
        "a": "`if value is None:` — identity, not `==`. Use a sentinel default (`def f(x=None)`) and treat `None` as 'not provided'.\n\n"
             "`if not value:` also catches `0`, `''`, `[]` and `False`, which is often not what you mean. `or` fallbacks turn `0` into your default, a classic bug: use `if value is None` explicitly.",
        "tags": ["python", "none", "conditionals", "bugs"],
    },
    {
        "q": ["how do i use enumerate and zip together in python",
              "python loop two lists at once",
              "python iterate two lists in parallel"],
        "a": "`for index, (a, b) in enumerate(zip(list_a, list_b), start=1):` — zip pairs, enumerate numbers the pairs.\n\n"
             "`zip` stops at the shortest input; add `strict=True` (3.10+) to raise instead of silently truncating. For a dict from two lists: `dict(zip(keys, values))`.",
        "tags": ["python", "loops", "zip", "enumerate"],
    },
    {
        "q": ["how do i flatten a list of lists in python",
              "python combine nested lists",
              "python chain lists"],
        "a": "`[item for row in rows for item in row]` for one level; `itertools.chain.from_iterable(rows)` when you only iterate once. For arbitrary depth, write a recursive generator.\n\n"
             "`sum(rows, [])` works but is quadratic — do not use it on real data.",
        "tags": ["python", "lists", "itertools", "idioms"],
    },
    {
        "q": ["how do i reverse a list or string in python",
              "python reverse string",
              "python list reversed"],
        "a": "`s[::-1]` reverses a string or list (a copy); `items.reverse()` reverses a list in place; `reversed(items)` iterates backwards without copying.\n\n"
             "For a string you cannot reverse in place — strings are immutable. `''.join(reversed(text))` is the explicit version.",
        "tags": ["python", "strings", "lists", "slicing"],
    },
    {
        "q": ["what does the walrus operator do in python",
              "python := operator",
              "python assignment expression"],
        "a": "`:=` assigns and returns in one expression, useful in conditions and comprehensions:\n\n```python\nwhile (line := f.readline()):\n    process(line)\n\nif (match := pattern.search(text)):\n    print(match.group(1))\n```\n\n"
             "Python 3.8+. Do not use it just to save a line; it earns its place when the value is both tested and used.",
        "tags": ["python", "syntax", "walrus", "idioms"],
    },
    {
        "q": ["what is a lambda in python",
              "python anonymous function",
              "how do i write a one line function"],
        "a": "A lambda is an expression-level function with one expression body: `sorted(rows, key=lambda row: row['age'])`.\n\n"
             "Use it for short keys and callbacks; for anything with logic or a name, write a `def`. Lambdas cannot contain statements, and the `key=` argument is usually the only place they belong.",
        "tags": ["python", "lambda", "functions", "idioms"],
    },
    {
        "q": ["what are f string format specifiers in python",
              "python format alignment padding",
              "python f string width"],
        "a": "After the colon: `:.2f` precision, `:>10` right-align, `:<10` left, `:^10` centre, `:04d` zero-pad, `:,` thousands, `:+` sign, `:%` percent, `:x` hex.\n\n"
             "Combine them: `f'{value:>10,.2f}'`. A fill character goes before the alignment: `f'{name:*^20}'`.",
        "tags": ["python", "f-strings", "formatting", "strings"],
    },
    {
        "q": ["how do i check if a string is a number in python",
              "python isdigit isalpha",
              "python validate numeric input"],
        "a": "`text.strip().replace('.', '', 1).replace('-', '', 1).isdigit()` is the quick test, but `float(text)` in a try/except is more honest and handles exponents.\n\n"
             "`str.isdigit()` accepts Unicode digits like '²'; `isnumeric()` is broader still. For money, `Decimal` rejects junk for you.",
        "tags": ["python", "strings", "validation", "numbers"],
    },
    {
        "q": ["how do i read a file in chunks in python",
              "python read big file in pieces",
              "python streaming file read"],
        "a": "```python\nwith open('big.bin', 'rb') as f:\n    while chunk := f.read(64 * 1024):\n        consume(chunk)\n```\n\n"
             "Read in binary for byte work. For text, iterate lines (that is already streaming) or use `f.read(4096)` with a decoder if lines can be enormous.",
        "tags": ["python", "files", "streaming", "performance"],
    },
    {
        "q": ["how do i find the number of lines in a file in python",
              "python count lines in a file",
              "python line count fast"],
        "a": "`sum(1 for _ in open('app.log', encoding='utf-8'))` streams and counts without loading the file. `len(Path(p).read_text().splitlines())` is fine for small files.\n\n"
             "Counting `'\\n'` with `read_bytes().count(b'\\n')` is fastest but misses a last line without a newline, so add 1 when the file does not end with one.",
        "tags": ["python", "files", "counting", "performance"],
    },
    {
        "q": ["how do i change the working directory in python",
              "python os chdir",
              "python run script in another folder"],
        "a": "`os.chdir(path)` changes the process directory; better, avoid it — resolve paths relative to the script: `BASE = Path(__file__).resolve().parent` and use `BASE / 'data.csv'`.\n\n"
             "`__file__` is the script path, while the CWD is wherever the user ran it from. Relying on the CWD is the usual reason a script works in the editor and fails from the terminal.",
        "tags": ["python", "paths", "files", "script"],
    },
    {
        "q": ["how do i add a progress bar to a python script",
              "python print progress",
              "python progress on a long loop"],
        "a": "Without dependencies, print on the same line:\n\n```python\nfor index, item in enumerate(items, start=1):\n    work(item)\n    print(f'\\r{index}/{len(items)}', end='', flush=True)\nprint()\n```\n\n"
             "`end=''` and `flush=True` are what keep it on one line. For anything longer, `tqdm` is the standard package.",
        "tags": ["python", "output", "cli", "script"],
    },
    {
        "q": ["how do i make python faster",
              "python speed up a script",
              "python performance tips"],
        "a": "Measure first (`cProfile`, `time.perf_counter`), then: move work out of loops, use set/dict lookups instead of list scans, let C handle bulk work (`join`, `sum`, `sorted`), avoid string `+=` in loops, and read files in one go when they are small.\n\n"
             "Typical wins: a dict instead of repeated list scans, `collections.Counter` instead of manual counting, and batching IO. Reach for numpy or an external process only after profiling says so.",
        "tags": ["python", "performance", "optimisation", "tools"],
    },
    {
        "q": ["how do i install and use requests in python",
              "python requests get example",
              "python http client library"],
        "a": "`python -m pip install requests`, then:\n\n```python\nimport requests\n\nresponse = requests.get('https://api.example.com/items', timeout=10)\nresponse.raise_for_status()\ndata = response.json()\n```\n\n"
             "Pass `timeout` on every call — requests has none by default. `params={}` builds the query string, `json=` sends JSON. The standard library equivalent is `urllib.request`.",
        "tags": ["python", "requests", "network", "http"],
    },
    {
        "q": ["how do i use pandas to read a csv",
              "python pandas read csv",
              "python dataframe basics"],
        "a": "```python\nimport pandas as pd\n\ndf = pd.read_csv('sales.csv')\nprint(df.head())\nprint(df['amount'].sum())\nprint(df.groupby('region')['amount'].sum().sort_values(ascending=False))\ndf.to_json('sales.json', orient='records', indent=2)\n```\n\n"
             "pandas is a third-party package (`pip install pandas`) and worth it for grouping, joins and cleaning. For a one-off file transform, the `csv` module avoids the dependency.",
        "tags": ["python", "pandas", "csv", "data"],
    },
    {
        "q": ["why does my python script do nothing when double clicked",
              "python script closes immediately windows",
              "python window flashes and disappears"],
        "a": "The console closes as soon as the process exits, so you never see the error. Run it from a terminal (`py script.py`) to read the traceback.\n\n"
             "If you need a windowed app, add `input('Press Enter to close')` at the end while testing, or build a real GUI. On Windows, `pythonw.exe` hides console output entirely — that is why nothing appears.",
        "tags": ["python", "windows", "errors", "script"],
    },
    {
        "q": ["how do i schedule a python script to run daily",
              "python cron job",
              "run a python script every day"],
        "a": "Use the operating system, not a `while True` loop: `cron` on Linux/macOS (`0 7 * * * /usr/bin/python3 /path/script.py >> /var/log/job.log 2>&1`), Task Scheduler on Windows, or a systemd timer.\n\n"
             "Always use absolute paths and the interpreter inside your venv, and log stdout and stderr — unattended failures are silent otherwise.",
        "tags": ["python", "automation", "cron", "script"],
    },
    {
        "q": ["how do i emit a csv sorted by date in python",
              "python sort by date string",
              "python parse dates in a csv"],
        "a": "Parse to `datetime.date` in the key, never sort date strings in mixed formats:\n\n```python\nfrom datetime import datetime\n\ndef key(row):\n    return datetime.strptime(row['date'], '%Y-%m-%d').date()\n\nrows.sort(key=key)\n```\n\n"
             "Mixed formats need `datetime.fromisoformat` with a fallback, or normalise the column during import.",
        "tags": ["python", "csv", "dates", "sorting"],
    },
    {
        "q": ["how do i count how many times a value appears in a csv in python",
              "python csv group count",
              "python tally column values"],
        "a": "```python\nimport csv\nfrom collections import Counter\n\nwith open('orders.csv', newline='', encoding='utf-8') as f:\n    counts = Counter(row['status'] for row in csv.DictReader(f))\n\nfor status, count in counts.most_common():\n    print(f'{status:<12} {count}')\n```\n\n"
             "`Counter` on a generator avoids building the full row list. Add `.strip().lower()` to the value if the column is inconsistent.",
        "tags": ["python", "csv", "counter", "counting"],
    },
    {
        "q": ["how do i remove empty rows from a csv in python",
              "python csv filter blank lines",
              "python clean a csv file"],
        "a": "```python\nimport csv\n\nwith open('in.csv', newline='', encoding='utf-8') as src, \\\n     open('out.csv', 'w', newline='', encoding='utf-8') as dst:\n    reader = csv.DictReader(src)\n    writer = csv.DictWriter(dst, fieldnames=reader.fieldnames)\n    writer.writeheader()\n    for row in reader:\n        if any((value or '').strip() for value in row.values()):\n            writer.writerow({k: (v or '').strip() for k, v in row.items()})\n```\n\n"
             "`newline=''` on both files is what stops blank lines appearing between rows on Windows.",
        "tags": ["python", "csv", "cleaning", "files"],
    },
    {
        "q": ["how do i print a table in the terminal with python",
              "python align columns output",
              "python text table"],
        "a": "```python\nrows = [('Ada', 91), ('Alan', 88)]\nfor name, score in rows:\n    print(f'{name:<10}{score:>6}')\n```\n\n"
             "Work out the width from the data when it varies: `width = max(len(str(row[0])) for row in rows)`. `textwrap` handles long cells, and `pprint` handles nested values.",
        "tags": ["python", "output", "formatting", "cli"],
    },
    {
        "q": ["how do i make a python script wait between steps",
              "python sleep example",
              "python delay in a loop"],
        "a": "`import time; time.sleep(1.5)` pauses the thread. For scheduling, compute the next timestamp instead of accumulating sleeps, which drift:\n\n```python\nimport time\nnext_run = time.monotonic() + 60\nwhile True:\n    time.sleep(max(0, next_run - time.monotonic()))\n    work()\n    next_run += 60\n```\n\n"
             "`asyncio.sleep` is the async equivalent; never call `time.sleep` inside async code.",
        "tags": ["python", "sleep", "time", "script"],
    },
    {
        "q": ["how do i handle unicode and encoding errors in python",
              "python unicodedecodeerror",
              "python utf-8 encoding problem"],
        "a": "Decode explicitly: `open(path, encoding='utf-8')`. For unknown input use `errors='replace'` (or `'ignore'`) and check what you got.\n\n"
             "`UnicodeDecodeError: 'utf-8' codec can't decode byte 0xff` means the file is not UTF-8 — find the real encoding, do not guess `latin-1` blindly. When printing to a legacy console, `sys.stdout.reconfigure(encoding='utf-8')` helps.",
        "tags": ["python", "unicode", "encoding", "errors"],
    },
    {
        "q": ["how do i merge two csv files in python",
              "python join two csv by a column",
              "python combine csv data"],
        "a": "```python\nimport csv\n\ndef load(path, key):\n    with open(path, newline='', encoding='utf-8') as f:\n        return {row[key]: row for row in csv.DictReader(f)}\n\nleft = load('orders.csv', 'id')\nright = load('customers.csv', 'id')\nfor key, row in left.items():\n    row.update(right.get(key, {}))\n```\n\n"
             "This is a left join in a dict. Watch duplicate keys (last wins) and strip whitespace from key columns before matching.",
        "tags": ["python", "csv", "join", "data"],
    },
    {
        "q": ["how do i split a csv into smaller files in python",
              "python chunk a csv",
              "python split csv into batches"],
        "a": "```python\nimport csv\nfrom itertools import islice\n\nwith open('big.csv', newline='', encoding='utf-8') as f:\n    reader = csv.DictReader(f)\n    fields = reader.fieldnames\n    part = 1\n    while rows := list(islice(reader, 10000)):\n        with open(f'part-{part:02d}.csv', 'w', newline='', encoding='utf-8') as out:\n            writer = csv.DictWriter(out, fieldnames=fields)\n            writer.writeheader()\n            writer.writerows(rows)\n        part += 1\n```\n\n"
             "The walrus-plus-islice pattern streams the source without loading it all, and stops cleanly at the end.",
        "tags": ["python", "csv", "files", "itertools"],
    },
]


def snippet(text):
    """Return the first ```python block, used only for compile checks."""
    match = re.search(r"```python\n(.*?)```", text, re.S)
    return match.group(1) if match else None


def check_python(text, where):
    block = snippet(text)
    if block is None:
        return
    try:
        ast.parse(block)
    except SyntaxError as error:
        raise SystemExit(f"{where}: does not compile: {error}")


def slug(text, limit=28):
    out = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (out or "record")[:limit]


def record(prefix, index, question, answer, tags, source):
    return {
        "id": f"{prefix}-{index:04d}-{slug(question, 24)}",
        "kind": "qa",
        "input": " ".join(question.split()),
        "output": answer.strip(),
        "tags": tags,
        "source": source,
    }


def load_seed():
    records = []
    for line in SEED.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        raw = json.loads(line)
        if raw.get("kind") == "pack":
            continue
        records.append(
            record("seed", len(records) + 1, raw.get("input") or raw.get("title") or "", raw.get("output") or raw.get("text") or "", raw.get("tags") or [], "seed")
        )
    return records


PHRASINGS = [
    "write a python script that {desc}",
    "python script to {desc}",
    "how do i {desc} in python",
    "write python code to {desc}",
    "can you write a python program that {desc}",
    "python code to {desc}",
    "show me a python script that {desc}",
    "how can i {desc} with python",
    "python program to {desc}",
    "i need a python script to {desc}",
    "give me python code that can {desc}",
]


def filled(recipe, params):
    """Return (desc, code) for one parameter set."""
    desc = recipe["desc"]
    code = recipe["code"]
    for key, value in params.items():
        desc = desc.replace(f"<<{key}>>", value)
        code = code.replace(f"<<{key}>>", value)
    return desc, code


def recipe_answer(desc, code):
    return f"{desc[0].upper()}{desc[1:]}:\n\n```python\n{code.strip()}\n```\n\nRun it with `python <file>.py`."


def build_recipes():
    records = []
    for recipe in RECIPES:
        for params in recipe["params"]:
            desc, code = filled(recipe, params)
            check_python(code, recipe["name"])
            answer = recipe_answer(desc, code)
            for template in PHRASINGS:
                question = template.format(desc=desc)
                records.append(
                    record("py-recipe", len(records) + 1, question, answer, recipe["tags"] + ["recipe"], "recipes")
                )
    return records


def build_concepts():
    records = []
    extras = [
        "python: {q}",
        "explain in python: {q}",
        "what is the best way to {q} in python",
        "beginner python question: {q}",
    ]
    for concept in CONCEPTS:
        for question in concept["q"]:
            check_python(concept["a"], question)
            records.append(
                record("py-concept", len(records) + 1, question, concept["a"], concept["tags"], "concepts")
            )
            for template in extras:
                records.append(
                    record("py-concept", len(records) + 1, template.format(q=question), concept["a"], concept["tags"], "concepts")
                )
    return records


def summary_of(obj):
    doc = inspect.getdoc(obj) or ""
    if not doc:
        return ""
    first = doc.split("\n\n")[0]
    first = " ".join(first.split())
    if len(first) > 190:
        first = first[:187].rstrip() + "..."
    return first


def signature_of(obj, qualname):
    try:
        return f"{qualname}{inspect.signature(obj)}"
    except (TypeError, ValueError):
        return qualname


def build_stdlib(limit=5000):
    import builtins

    records = []
    skip_classes = {"type", "object"}

    for module_name in MODULES:
        if len(records) >= limit:
            break
        try:
            module = importlib.import_module(module_name)
        except Exception:
            continue
        taken = 0
        for name, obj in sorted(vars(module).items()):
            if name.startswith("_") or taken >= 60:
                continue
            if not (inspect.isfunction(obj) or inspect.isbuiltin(obj) or inspect.isclass(obj)):
                continue
            if inspect.isclass(obj) and name in skip_classes:
                continue
            owner = getattr(obj, "__module__", module.__name__) or module.__name__
            if inspect.isclass(obj) and owner.split(".")[0] != module_name.split(".")[0]:
                continue
            summary = summary_of(obj)
            if len(summary) < 12:
                continue
            qual = f"{module_name}.{name}"
            answer = f"`{signature_of(obj, qual)}`\n\n{summary}"
            tags = ["python", "stdlib", module_name.replace(".", "-")]
            kind = "class" if inspect.isclass(obj) else "function"
            tags.append(kind)
            for question in (
                f"what does {qual} do in python",
                f"how do i use {qual} in python",
                f"python {qual} example",
                f"what is {qual}",
                f"{qual} documentation python",
            ):
                records.append(record("py-api", len(records) + 1, question, answer, tags, "stdlib"))
            taken += 1

    for type_name in BUILTIN_TYPES:
        cls = getattr(builtins, type_name)
        for name, obj in sorted(vars(cls).items()):
            if name.startswith("_"):
                continue
            doc = inspect.getdoc(obj) or ""
            if not doc:
                continue
            summary = " ".join(doc.split("\n\n")[0].split())
            if len(summary) < 12:
                continue
            qual = f"{type_name}.{name}"
            answer = f"`{signature_of(obj, qual)}`\n\n{summary}\n\nA method on every `{type_name}` in Python."
            tags = ["python", "method", type_name]
            for question in (
                f"what does {qual} do in python",
                f"how do i use {qual} in python",
                f"python {type_name} {name} example",
                f"what is {qual}",
                f"{type_name}.{name} python documentation",
            ):
                records.append(record("py-method", len(records) + 1, question, answer, tags, "stdlib"))
    return records


def dedupe(records):
    seen = set()
    out = []
    for rec in records:
        key = rec["input"].lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(rec)
    return out


def main():
    records = []
    records += load_seed()
    recipes = build_recipes()
    records += recipes
    records += build_concepts()
    stdlib = build_stdlib()
    records += stdlib
    records = dedupe(records)
    print(f"seed {len(load_seed())}, recipes {len(recipes)}, stdlib {len(stdlib)}, unique {len(records)}")

    if len(records) < TARGET:
        # Extra phrasings for the same answers, so natural descriptions still
        # reach the right record. Scripts first: they are what people ask for.
        extra = ["python code {desc}", "show me python that {desc}", "{desc} python script example"]
        pool = []
        for recipe in RECIPES:
            for params in recipe["params"]:
                desc, code = filled(recipe, params)
                answer = recipe_answer(desc, code)
                for template in extra:
                    pool.append(record("py-recipe", 0, template.format(desc=desc), answer, recipe["tags"] + ["recipe"], "recipes"))
        records += dedupe(pool)
        print(f"after extra recipe phrasings: {len(records)}")

    if len(records) < TARGET:
        more = ["python {qual} syntax", "how does {qual} work in python", "explain {qual} in python"]
        extra_api = []
        for rec in stdlib:
            qual = rec["input"].replace("what does ", "").replace(" do in python", "").strip()
            for template in more:
                extra_api.append(record("py-api", 0, template.format(qual=qual), rec["output"], rec["tags"], "stdlib"))
        records += dedupe(extra_api)
        print(f"after extra stdlib phrasings: {len(records)}")

    if len(records) > TARGET:
        records = records[:TARGET]
    if len(records) != TARGET:
        raise SystemExit(f"only produced {len(records)} records, need {TARGET}")

    for index, rec in enumerate(records, start=1):
        rec["id"] = f"{rec['id'].split('-')[0]}-{index:05d}"
        check_python(rec["output"], rec["id"])

    OUT.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n", encoding="utf-8")
    size = OUT.stat().st_size
    print(f"wrote {len(records)} records, {size / 1024:.0f} KB to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

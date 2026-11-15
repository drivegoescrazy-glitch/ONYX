/* ONYX core engine: training-data parsing, BM25 retrieval and prompt building.
   Shared by the browser app; loadable in Node for parity checks against the CLI. */
var OnyxCore = (function () {
  'use strict';

  var VERSION = '1.2.0';

  var STOPWORDS = new Set((
    'the a an and or of to in is are was were be been being with as at by it this ' +
    'that from on i you my we us them into me our he she him her his ' +
    'how what when where which who whom why do does did done can could should would will ' +
    'shall may might must about if then than so but not no any all some more most ' +
    'here these those very just also please tell need want much many same only use used ' +
    'using make made get got give let work works thing things way best'
  ).split(' '));

  var JSON_KEYS = ['records', 'data', 'examples', 'items', 'training_data', 'train'];
  var CHUNK = 1200;

  /* ---------------------------------------------------------------- text ---- */

  function tokenize(text) {
    var words = String(text == null ? '' : text).toLowerCase().match(/[a-z0-9_]+/g) || [];
    var out = [];
    for (var i = 0; i < words.length; i++) {
      var w = words[i];
      if (w.length === 1 && !(w >= '0' && w <= '9')) continue;
      if (STOPWORDS.has(w)) continue;
      out.push(stem(w));
    }
    return out;
  }

  function stem(w) {
    if (w.length > 5 && w.endsWith('ing')) w = w.slice(0, -3);
    else if (w.length > 4 && w.endsWith('ed') && !w.endsWith('eed')) w = w.slice(0, -2);
    else if (w.length > 4 && w.endsWith('es')) w = w.slice(0, -2);
    else if (w.length > 4 && w.endsWith('s') && !w.endsWith('ss') && !w.endsWith('us') && !w.endsWith('is')) w = w.slice(0, -1);
    if (w.length > 4 && w.endsWith('e')) w = w.slice(0, -1);
    return w;
  }

  function firstLine(s, limit) {
    s = String(s == null ? '' : s).trim();
    var nl = s.indexOf('\n');
    if (nl >= 0) s = s.slice(0, nl).trim();
    return s.length > limit ? s.slice(0, limit).trim() + '…' : s;
  }

  function slug(s) {
    var out = String(s == null ? '' : s).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');
    if (!out) out = 'record';
    return out.slice(0, 40);
  }

  /* ------------------------------------------------------------- records ---- */

  function trimStr(v) { return v == null ? '' : String(v).trim(); }

  function firstNonEmpty() {
    for (var i = 0; i < arguments.length; i++) {
      if (arguments[i] != null && String(arguments[i]).trim() !== '') return String(arguments[i]);
    }
    return '';
  }

  function searchText(rec) {
    var parts = [rec.title, rec.input, rec.output, rec.text, (rec.tags || []).join(' ')];
    var kept = [];
    for (var i = 0; i < parts.length; i++) {
      if (parts[i] && String(parts[i]).trim() !== '') kept.push(String(parts[i]));
    }
    return kept.join('\n').trim();
  }

  function indexText(rec) {
    return [searchText(rec), rec.input || '', rec.title || '', (rec.tags || []).join(' ')].join('\n');
  }

  function label(rec) {
    var candidate = [rec.title, rec.input, rec.text, rec.output, rec.id];
    for (var i = 0; i < candidate.length; i++) {
      if (candidate[i] && String(candidate[i]).trim() !== '') return firstLine(candidate[i], 88);
    }
    return rec.id || 'record';
  }

  function body(rec) {
    return trimStr(rec.output) || trimStr(rec.text) || trimStr(rec.input);
  }

  function recordKey(rec) {
    var norm = [trimStr(rec.input), trimStr(rec.output), trimStr(rec.text), trimStr(rec.title)]
      .join('\u0000').toLowerCase();
    var h1 = 0x811c9dc5, h2 = 0x1000193;
    for (var i = 0; i < norm.length; i++) {
      var c = norm.charCodeAt(i);
      h1 = (h1 ^ c) * 0x01000193 >>> 0;
      h2 = (h2 + c * (i + 7)) >>> 0;
    }
    return ('00000000' + h1.toString(16)).slice(-8) + ('00000000' + h2.toString(16)).slice(-8);
  }

  function parseTags(raw) {
    if (raw == null) return [];
    var list = [];
    if (Array.isArray(raw)) list = raw.map(trimStr);
    else if (typeof raw === 'string') list = raw.split(',');
    else return [];
    var out = [], seen = {};
    for (var i = 0; i < list.length; i++) {
      var t = trimStr(list[i]);
      if (!t) continue;
      var key = t.toLowerCase();
      if (seen[key]) continue;
      seen[key] = true;
      out.push(t);
    }
    return out;
  }

  function parseRecord(obj) {
    if (!obj || typeof obj !== 'object' || Array.isArray(obj)) throw new Error('not a JSON object');
    var input = firstNonEmpty(obj.input, obj.question, obj.prompt, obj.instruction);
    var output = firstNonEmpty(obj.output, obj.answer, obj.completion, obj.response);
    var text = firstNonEmpty(obj.text, obj.content, obj.body);
    var title = firstNonEmpty(obj.title, obj.topic);
    if (!output && !text) text = firstNonEmpty(obj.description);

    var messages = Array.isArray(obj.messages) ? obj.messages : [];
    for (var i = 0; i < messages.length; i++) {
      var m = messages[i];
      if (!m) continue;
      var content = trimStr(m.content);
      if (!content) continue;
      switch (trimStr(m.role).toLowerCase()) {
        case 'user':
        case 'human':
          input = input ? input + '\n\n' + content : content;
          break;
        case 'assistant':
        case 'model':
        case 'gpt':
          output = content;
          break;
        case 'system':
          if (!title) title = firstLine(content, 80);
          break;
      }
    }

    var rec = {
      id: trimStr(obj.id),
      kind: trimStr(obj.kind),
      title: trimStr(title),
      input: trimStr(input),
      output: trimStr(output),
      text: trimStr(text),
      tags: parseTags(obj.tags),
      source: trimStr(obj.source)
    };
    if (!rec.kind) rec.kind = rec.text && !rec.output ? 'doc' : 'qa';
    if (!rec.text && !rec.output) throw new Error('needs "input"+"output" or "text"');
    return rec;
  }

  /* -------------------------------------------------------------- parsing ---- */

  function parseJSONL(content) {
    var lines = String(content || '').split(/\r?\n/);
    var records = [], skipped = 0, warnings = [];
    for (var i = 0; i < lines.length; i++) {
      var raw = lines[i].trim();
      if (!raw || raw.indexOf('//') === 0 || raw.indexOf('#') === 0) continue;
      try {
        records.push(parseRecord(JSON.parse(raw)));
      } catch (err) {
        skipped++;
        if (warnings.length < 3) warnings.push('line ' + (i + 1) + ': ' + err.message);
      }
    }
    return { records: records, skipped: skipped, warnings: warnings };
  }

  function recordsFromList(list) {
    var records = [], skipped = 0, warnings = [];
    for (var i = 0; i < list.length; i++) {
      try {
        records.push(parseRecord(list[i]));
      } catch (err) {
        skipped++;
        if (warnings.length < 3) warnings.push('entry ' + (i + 1) + ': ' + err.message);
      }
    }
    return { records: records, skipped: skipped, warnings: warnings };
  }

  function parseJSON(content) {
    var parsed;
    try {
      parsed = JSON.parse(content);
    } catch (err) {
      return parseJSONL(content);
    }
    if (Array.isArray(parsed)) return recordsFromList(parsed);
    if (parsed && typeof parsed === 'object') {
      for (var i = 0; i < JSON_KEYS.length; i++) {
        if (Array.isArray(parsed[JSON_KEYS[i]])) return recordsFromList(parsed[JSON_KEYS[i]]);
      }
      try {
        return { records: [parseRecord(parsed)], skipped: 0, warnings: [] };
      } catch (err2) {
        return { records: [], skipped: 1, warnings: [err2.message] };
      }
    }
    return { records: [], skipped: 1, warnings: ['expected an object or array of records'] };
  }

  function chunkText(content) {
    var text = String(content || '').replace(/\r\n/g, '\n');
    var chunks = [], current = '';
    function flush() {
      var trimmed = current.trim();
      if (trimmed) chunks.push(trimmed);
      current = '';
    }
    var paras = text.split(/\n{2,}/);
    for (var i = 0; i < paras.length; i++) {
      var para = paras[i].trim();
      if (!para) continue;
      if (current.length > 0 && current.length + para.length > CHUNK) flush();
      while (para.length > CHUNK * 3) {
        chunks.push(para.slice(0, CHUNK * 3).trim());
        para = para.slice(CHUNK * 3).trim();
      }
      if (!para) continue;
      if (current.length > 0) current += '\n\n';
      current += para;
    }
    flush();
    return chunks;
  }

  function parseText(content, name) {
    var base = String(name || 'pack').split(/[\\/]/).pop() || 'pack';
    var chunks = chunkText(content);
    var records = [];
    for (var i = 0; i < chunks.length; i++) {
      var title = base;
      if (chunks.length > 1) title = base + ' (' + (i + 1) + '/' + chunks.length + ')';
      records.push({
        id: slug(base) + '-' + ('0' + (i + 1)).slice(-2),
        kind: 'doc',
        title: title,
        input: '',
        output: '',
        text: chunks[i],
        tags: [],
        source: String(name || base)
      });
    }
    return records;
  }

  function extension(name) {
    var m = String(name || '').toLowerCase().match(/\.[^./\\]+$/);
    return m ? m[0] : '';
  }

  function parseFileContent(name, content) {
    var text = String(content == null ? '' : content).replace(/^\uFEFF/, '');
    var ext = extension(name);
    if (ext === '.jsonl' || ext === '.ndjson') return parseJSONL(text);
    if (ext === '.json') return parseJSON(text);
    if (ext === '.txt' || ext === '.md' || ext === '.markdown') {
      return { records: parseText(text, name), skipped: 0, warnings: [] };
    }
    if (text.trim().charAt(0) === '{' || text.trim().charAt(0) === '[') return parseJSON(text);
    return { records: parseText(text, name), skipped: 0, warnings: [] };
  }

  function merge(base, add) {
    var seen = {}, records = [], dupes = 0, added = 0;
    for (var i = 0; i < base.length; i++) {
      var key = recordKey(base[i]);
      if (seen[key]) continue;
      seen[key] = true;
      records.push(base[i]);
    }
    for (var j = 0; j < add.length; j++) {
      var k = recordKey(add[j]);
      if (seen[k]) { dupes++; continue; }
      seen[k] = true;
      records.push(add[j]);
      added++;
    }
    return { records: records, added: added, dupes: dupes };
  }

  /* --------------------------------------------------------------- index ---- */

  function termSet(terms) {
    var set = new Set();
    for (var i = 0; i < terms.length; i++) set.add(terms[i]);
    return set;
  }

  function buildIndex(records) {
    var index = { records: records, tf: [], lens: [], tags: [], asks: [], df: new Map(), avgdl: 0, terms: 0 };
    var total = 0;
    for (var i = 0; i < records.length; i++) {
      var rec = records[i];
      var terms = tokenize(indexText(rec));
      var tf = new Map();
      for (var t = 0; t < terms.length; t++) tf.set(terms[t], (tf.get(terms[t]) || 0) + 1);
      index.tf.push(tf);
      index.lens.push(terms.length);
      total += terms.length;
      index.tags.push(termSet(tokenize((rec.tags || []).join(' '))));
      index.asks.push(termSet(tokenize((rec.title || '') + ' ' + (rec.input || ''))));
      tf.forEach(function (_count, term) {
        index.df.set(term, (index.df.get(term) || 0) + 1);
      });
    }
    index.terms = index.df.size;
    index.avgdl = records.length ? total / records.length : 0;
    return index;
  }

  function expand(index, terms) {
    var out = [], seen = {};
    for (var i = 0; i < terms.length; i++) {
      var term = terms[i];
      if (seen[term]) continue;
      seen[term] = true;
      if (index.df.get(term)) out.push({ text: term, weight: 1 });
      if (term.length < 4) continue;
      var matched = 0;
      var iterator = index.df.keys();
      for (var step = iterator.next(); !step.done; step = iterator.next()) {
        var candidate = step.value;
        if (seen[candidate] || candidate.length <= term.length || candidate.indexOf(term) !== 0) continue;
        seen[candidate] = true;
        out.push({ text: candidate, weight: 0.4 });
        matched++;
        if (matched >= 40) break;
      }
    }
    return out;
  }

  function search(index, query, k) {
    if (!index || !index.records.length) return [];
    k = k || 6;
    var terms = tokenize(query);
    if (!terms.length) return [];
    var n = index.records.length;
    var scores = new Array(n).fill(0);
    var k1 = 1.4, b = 0.75;
    var weighted = expand(index, terms);
    for (var w = 0; w < weighted.length; w++) {
      var weight = weighted[w];
      var df = index.df.get(weight.text);
      if (!df) continue;
      var idf = Math.log(1 + (n - df + 0.5) / (df + 0.5)) * weight.weight;
      for (var i = 0; i < n; i++) {
        var f = index.tf[i].get(weight.text);
        if (!f) continue;
        var dl = index.lens[i];
        if (!dl) continue;
        scores[i] += idf * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / index.avgdl));
      }
    }
    var unique = termSet(terms);
    unique.forEach(function (term) {
      for (var i = 0; i < n; i++) {
        if (index.tags[i].has(term)) scores[i] += 1.5;
        if (index.asks[i].has(term)) scores[i] += 0.7;
      }
    });
    var phrase = String(query == null ? '' : query).toLowerCase().trim();
    if (phrase.length > 3) {
      for (var j = 0; j < n; j++) {
        if (searchText(index.records[j]).toLowerCase().indexOf(phrase) >= 0) scores[j] += 2.5;
      }
    }
    var hits = [];
    for (var h = 0; h < n; h++) {
      if (scores[h] > 0) hits.push({ record: index.records[h], score: scores[h] });
    }
    hits.sort(function (a, c) { return c.score - a.score; });
    return hits.slice(0, k);
  }

  /* ------------------------------------------------------------- answers ---- */

  function truncateBody(text) {
    var bodyText = trimStr(text);
    return bodyText.length > 2000 ? bodyText.slice(0, 2000).trim() + '…' : bodyText;
  }

  function retrievalAnswer(hits) {
    if (!hits.length) {
      return 'I do not know that one yet — I only answer from what I have been trained on. Open /train, drop a JSONL pack in, and ask me again.';
    }
    return truncateBody(body(hits[0].record));
  }

  function systemPrompt(records, hits) {
    var lines = [
      'You are ONYX, a coding agent running locally on the user\'s machine.',
      'Talk like a person: plain sentences, no preamble, no headings.',
      'Never show your reasoning, planning, sources or "thinking" — reply only with the answer.',
      'When code helps, give one short runnable block and one line about how to run it.',
      'Treat the trained knowledge records below as ground truth when they are relevant.',
      'If they do not cover the question, say so in one sentence and then answer from general knowledge.',
      'Never pretend you ran a command or browsed the web.',
      '',
      'The app holds ' + records.length + ' trained records.'
    ];
    if (!hits.length) {
      lines.push('', 'No trained records matched this question.');
      return lines.join('\n');
    }
    lines.push('', '<knowledge>');
    for (var i = 0; i < hits.length; i++) {
      var rec = hits[i].record;
      var tags = rec.tags && rec.tags.length ? ', tags: ' + rec.tags.join(', ') : '';
      lines.push('[' + (i + 1) + '] ' + label(rec) + ' (id: ' + rec.id + tags + ')');
      if (trimStr(rec.input)) lines.push('Q: ' + trimStr(rec.input));
      var answerBody = truncateBody(body(rec));
      if (answerBody.length > 1400) answerBody = answerBody.slice(0, 1400).trim() + '…';
      lines.push('A: ' + answerBody, '');
    }
    lines.push('</knowledge>');
    return lines.join('\n');
  }

  /* ------------------------------------------------------------ programs ---- */

  var PROGRAM_WORDS = /\b(python|\.py|script|program|cli|command[- ]line tool|function)\b/;
  var PROGRAM_ASKS = /\b(write|make|create|build|generate|give me|i need|we need|code me|help me write|show me how to write)\b/;
  var QUESTION_START = /^(how|what|why|when|where|who|which|should|is|are|can you explain|explain|difference)\b/;

  function wantsProgram(query) {
    var text = String(query == null ? '' : query).toLowerCase().trim();
    if (!text || !PROGRAM_WORDS.test(text) || !PROGRAM_ASKS.test(text)) return false;
    if (QUESTION_START.test(text) && !/\b(script|program)\b/.test(text)) return false;
    return true;
  }

  function fileHint(query, fallback) {
    var match = String(query).match(/[A-Za-z0-9_./-]+\.(txt|text|csv|json|log|md|dat|py)/);
    return match ? match[0] : fallback;
  }

  function columnHint(query, fallback) {
    var match = String(query).match(/column\s+["'`]?([A-Za-z0-9_]+)/i) ||
      String(query).match(/["'`]([A-Za-z0-9_]+)["'`]\s+column/i);
    return match ? match[1] : fallback;
  }

  var RECIPES = [
    {
      name: 'word count',
      keys: ['word count', 'count words', 'count the words', 'count word', 'wordcount', 'words in a file', 'word counter', 'count lines'],
      intro: 'Here is a script that counts the lines, words and unique words in a text file.',
      code: function () {
        return String.raw`#!/usr/bin/env python3
"""Count the lines, words and characters in a text file."""

import sys
from pathlib import Path


def count(path):
    text = Path(path).read_text(encoding="utf-8")
    words = text.split()
    return {
        "lines": text.count("\n") + (0 if text.endswith("\n") or not text else 1),
        "words": len(words),
        "characters": len(text),
        "unique_words": len({word.lower().strip(".,!?;:'()") for word in words}),
    }


def main():
    if len(sys.argv) != 2:
        print(f"usage: {Path(sys.argv[0]).name} FILE")
        return 1
    for name, value in count(sys.argv[1]).items():
        print(f"{name:>14}: {value:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())`;
      }
    },
    {
      name: 'word frequency',
      keys: ['most common words', 'word frequency', 'frequent words', 'top words', 'common words', 'which words'],
      intro: 'Here is a script that prints the words a text uses most, with the counts.',
      code: function () {
        return String.raw`#!/usr/bin/env python3
"""Print the most common words in a text file."""

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
    counts = Counter(word for word in words if word not in STOPWORDS)
    return counts.most_common(limit)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "input.txt"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    for word, count in top_words(path, limit):
        print(f"{word:<20} {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())`;
      }
    },
    {
      name: 'csv total',
      keys: ['csv', 'sum a column', 'sum column', 'total a column', 'add up a column', 'spreadsheet'],
      intro: 'Here is a script that sums one numeric column of a CSV and prints the total.',
      code: function (ctx) {
        return String.raw`#!/usr/bin/env python3
"""Sum one numeric column of a CSV file."""

import argparse
import csv


def summarise(path, column):
    total = 0.0
    rows = 0
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            raw = (row.get(column) or "").strip().replace(",", "")
            if not raw:
                continue
            try:
                total += float(raw)
            except ValueError:
                continue
            rows += 1
    return total, rows


def main():
    parser = argparse.ArgumentParser(description="Sum a CSV column")
    parser.add_argument("path", nargs="?", default="${ctx.file || 'data.csv'}")
    parser.add_argument("-c", "--column", default="${ctx.column || 'amount'}")
    args = parser.parse_args()

    total, rows = summarise(args.path, args.column)
    print(f"{rows} rows, total {args.column}: {total:,.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())`;
      }
    },
    {
      name: 'bulk rename',
      keys: ['rename', 'renaming', 'rename files', 'rename a folder'],
      intro: 'Here is a script that renames every file in a folder with a prefix and a running number. It prints the plan first and only renames with --apply.',
      code: function (ctx) {
        return String.raw`#!/usr/bin/env python3
"""Bulk-rename the files in a folder with a prefix and a running number."""

import argparse
from pathlib import Path


def rename(folder, prefix, apply):
    files = sorted(path for path in Path(folder).iterdir() if path.is_file())
    width = max(3, len(str(len(files))))
    for index, path in enumerate(files, start=1):
        target = path.with_name(f"{prefix}-{index:0{width}d}{path.suffix.lower()}")
        print(f"{path.name}  ->  {target.name}")
        if apply:
            path.rename(target)
    if not apply:
        print("\nDry run. Add --apply to rename for real.")


def main():
    parser = argparse.ArgumentParser(description="Rename files in a folder")
    parser.add_argument("folder", nargs="?", default="${ctx.folder || '.'}")
    parser.add_argument("-p", "--prefix", default="file")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    rename(args.folder, args.prefix, args.apply)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())`;
      }
    },
    {
      name: 'calculator',
      keys: ['calculator', 'calculate', 'arithmetic', 'math expression', 'math problem'],
      intro: 'Here is a calculator that parses arithmetic with the ast module instead of calling eval on raw input.',
      code: function () {
        return String.raw`#!/usr/bin/env python3
"""A small calculator that evaluates arithmetic safely."""

import ast
import operator

OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
}


def evaluate(node):
    if isinstance(node, ast.Expression):
        return evaluate(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in OPERATORS:
        return OPERATORS[type(node.op)](evaluate(node.left), evaluate(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in OPERATORS:
        return OPERATORS[type(node.op)](evaluate(node.operand))
    raise ValueError("only numbers and + - * / // % ** are allowed")


def calculate(expression):
    return evaluate(ast.parse(expression, mode="eval"))


def main():
    print("Calculator — type an expression, or 'quit' to stop.")
    while True:
        try:
            line = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if line.lower() in {"quit", "exit", "q"}:
            return 0
        if not line:
            continue
        try:
            print(calculate(line))
        except (ValueError, SyntaxError, ZeroDivisionError) as error:
            print(f"error: {error}")


if __name__ == "__main__":
    raise SystemExit(main())`;
      }
    },
    {
      name: 'fetch json',
      keys: ['fetch json', 'json api', 'call an api', 'from an api', 'http request', 'request json', 'api endpoint', 'json from a url'],
      intro: 'Here is a script that fetches JSON from a URL and prints it.',
      code: function () {
        return String.raw`#!/usr/bin/env python3
"""Fetch JSON from a URL and print it."""

import json
import sys
import urllib.request


def get_json(url, timeout=15):
    request = urllib.request.Request(url, headers={"User-Agent": "onyx-script/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def main():
    url = sys.argv[1] if len(sys.argv) > 1 else "https://api.github.com/repos/python/cpython"
    data = get_json(url)
    print(json.dumps(data, indent=2, ensure_ascii=False)[:4000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())`;
      }
    },
    {
      name: 'download',
      keys: ['download', 'fetch a file', 'save a file from', 'download a file'],
      intro: 'Here is a script that downloads a file in chunks instead of holding it all in memory.',
      code: function () {
        return String.raw`#!/usr/bin/env python3
"""Download a file from a URL, streaming it to disk."""

import sys
import urllib.request
from pathlib import Path


def download(url, target=None, chunk=64 * 1024):
    target = Path(target or url.rsplit("/", 1)[-1] or "download.bin")
    with urllib.request.urlopen(url, timeout=30) as response, target.open("wb") as out:
        total = 0
        while True:
            block = response.read(chunk)
            if not block:
                break
            out.write(block)
            total += len(block)
    return target, total


def main():
    if len(sys.argv) < 2:
        print("usage: download.py URL [TARGET]")
        return 1
    path, size = download(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
    print(f"saved {path} ({size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())`;
      }
    },
    {
      name: 'dedupe lines',
      keys: ['duplicate lines', 'dedupe', 'remove duplicates', 'duplicates in a file', 'unique lines'],
      intro: 'Here is a script that removes duplicate lines from a file, keeping the first one it sees.',
      code: function (ctx) {
        return String.raw`#!/usr/bin/env python3
"""Remove duplicate lines from a text file, keeping the first occurrence."""

import sys
from pathlib import Path


def dedupe(source, target=None):
    path = Path(source)
    lines = path.read_text(encoding="utf-8").splitlines()
    seen = set()
    unique = []
    for line in lines:
        if line in seen:
            continue
        seen.add(line)
        unique.append(line)
    destination = Path(target or f"{path.stem}-unique{path.suffix}")
    destination.write_text("\n".join(unique) + "\n", encoding="utf-8")
    return destination, len(lines) - len(unique)


def main():
    source = sys.argv[1] if len(sys.argv) > 1 else "${ctx.file || 'input.txt'}"
    destination, removed = dedupe(source, sys.argv[2] if len(sys.argv) > 2 else None)
    print(f"{removed} duplicate lines removed -> {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())`;
      }
    },
    {
      name: 'sort numbers',
      keys: ['sort', 'sorted numbers', 'sort a list', 'sort numbers', 'order numbers', 'ascending'],
      intro: 'Here is a script that reads numbers, sorts them and prints a summary.',
      code: function () {
        return String.raw`#!/usr/bin/env python3
"""Sort numbers and print a small summary."""

import sys


def numbers(text):
    values = []
    for piece in text.replace(",", " ").split():
        try:
            values.append(float(piece))
        except ValueError:
            continue
    return values


def main():
    text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("numbers: ")
    values = numbers(text)
    if not values:
        print("no numbers found")
        return 1
    ordered = sorted(values)
    print("sorted:", ", ".join(f"{value:g}" for value in ordered))
    print(f"sum: {sum(ordered):g}  min: {ordered[0]:g}  max: {ordered[-1]:g}")
    print(f"average: {sum(ordered) / len(ordered):g}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())`;
      }
    },
    {
      name: 'fizzbuzz',
      keys: ['fizzbuzz', 'fizz buzz'],
      intro: 'Here is FizzBuzz.',
      code: function () {
        return String.raw`#!/usr/bin/env python3
"""FizzBuzz: multiples of 3 are Fizz, of 5 are Buzz, of both are FizzBuzz."""

import sys


def fizzbuzz(limit=15):
    for number in range(1, limit + 1):
        if number % 15 == 0:
            yield "FizzBuzz"
        elif number % 3 == 0:
            yield "Fizz"
        elif number % 5 == 0:
            yield "Buzz"
        else:
            yield str(number)


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    print("\n".join(fizzbuzz(limit)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())`;
      }
    },
    {
      name: 'primes',
      keys: ['prime', 'primes', 'prime numbers'],
      intro: 'Here is a sieve that prints every prime below a limit.',
      code: function () {
        return String.raw`#!/usr/bin/env python3
"""Print every prime below a limit using a sieve."""

import sys


def primes_below(limit):
    if limit < 3:
        return []
    sieve = bytearray([1]) * limit
    sieve[0:2] = b"\x00\x00"
    for number in range(2, int(limit ** 0.5) + 1):
        if sieve[number]:
            start = number * number
            sieve[start::number] = bytearray(len(range(start, limit, number)))
    return [index for index, flag in enumerate(sieve) if flag]


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    found = primes_below(limit)
    print(f"{len(found)} primes below {limit}")
    print(", ".join(str(number) for number in found))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())`;
      }
    },
    {
      name: 'fibonacci',
      keys: ['fibonacci', 'fib numbers', 'fib'],
      intro: 'Here is a script that prints the first n Fibonacci numbers.',
      code: function () {
        return String.raw`#!/usr/bin/env python3
"""Print the first n Fibonacci numbers."""

import sys


def fibonacci(count):
    first, second = 0, 1
    for _ in range(count):
        yield first
        first, second = second, first + second


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    print(", ".join(str(number) for number in fibonacci(count)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())`;
      }
    },
    {
      name: 'palindrome',
      keys: ['palindrome', 'reads the same'],
      intro: 'Here is a palindrome checker that ignores case, spaces and punctuation.',
      code: function () {
        return String.raw`#!/usr/bin/env python3
"""Check whether a word or sentence is a palindrome."""

import re
import sys


def normalise(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def is_palindrome(text):
    cleaned = normalise(text)
    return cleaned == cleaned[::-1]


def main():
    try:
        text = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("text: ")
    except EOFError:
        print("no text given")
        return 1
    verdict = "is" if is_palindrome(text) else "is not"
    print(f'"{text}" {verdict} a palindrome')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())`;
      }
    },
    {
      name: 'password',
      keys: ['password', 'passphrase', 'strong random'],
      intro: 'Here is a password generator built on the secrets module, which is safe for real passwords.',
      code: function () {
        return String.raw`#!/usr/bin/env python3
"""Generate a strong random password."""

import secrets
import string
import sys

ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*()-_=+"


def password(length=20):
    # secrets is cryptographically secure, unlike random
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def main():
    length = int(sys.argv[1]) if len(sys.argv) > 1 else 20
    if length < 8:
        print("use at least 8 characters")
        return 1
    print(password(length))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())`;
      }
    },
    {
      name: 'timestamped log',
      keys: ['timestamp', 'log file', 'logging', 'write a log', 'journal', 'timestamps'],
      intro: 'Here is a script that appends a timestamped line to a log file.',
      code: function () {
        return String.raw`#!/usr/bin/env python3
"""Append a timestamped line to a log file."""

import sys
from datetime import datetime
from pathlib import Path

LOG = Path("notes.log")


def log(message):
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(f"{stamp}  {message}\n")
    return stamp


def main():
    message = " ".join(sys.argv[1:]) or "started"
    stamp = log(message)
    print(f"[{stamp}] {message}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())`;
      }
    },
    {
      name: 'search files',
      keys: ['search files', 'searches files', 'grep', 'find text', 'search text', 'search a folder', 'find a phrase', 'which file', 'search'],
      intro: 'Here is a small grep: it walks a folder and prints file:line for every match.',
      code: function (ctx) {
        return String.raw`#!/usr/bin/env python3
"""Search every text file under a folder for a phrase."""

import argparse
from pathlib import Path

SUFFIXES = {".txt", ".py", ".md", ".csv", ".json", ".log"}


def search(root, needle):
    matches = []
    for path in sorted(Path(root).rglob("*")):
        if not path.is_file() or path.suffix.lower() not in SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if needle.lower() in line.lower():
                matches.append((path, number, line.strip()))
    return matches


def main():
    parser = argparse.ArgumentParser(description="Search files for a phrase")
    parser.add_argument("needle")
    parser.add_argument("root", nargs="?", default="${ctx.folder || '.'}")
    args = parser.parse_args()

    matches = search(args.root, args.needle)
    for path, number, line in matches:
        print(f"{path}:{number}: {line}")
    print(f"\n{len(matches)} matches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())`;
      }
    },
    {
      name: 'json settings',
      keys: ['settings', 'config file', 'save settings', 'read json', 'json file', 'configuration'],
      intro: 'Here is a settings helper that reads a JSON file, fills in defaults and writes it back.',
      code: function (ctx) {
        return String.raw`#!/usr/bin/env python3
"""Read and update a small JSON settings file."""

import json
from pathlib import Path

SETTINGS = Path("${ctx.file || 'settings.json'}")
DEFAULTS = {"theme": "dark", "recent": [], "volume": 5}


def load():
    if not SETTINGS.exists():
        save(DEFAULTS)
        return dict(DEFAULTS)
    with SETTINGS.open(encoding="utf-8") as handle:
        data = json.load(handle)
    return {**DEFAULTS, **data}


def save(settings):
    SETTINGS.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def main():
    settings = load()
    print("current:", settings)
    settings["volume"] = 7
    settings["recent"].append("onyx")
    save(settings)
    print("saved to", SETTINGS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())`;
      }
    },
    {
      name: 'countdown',
      keys: ['countdown', 'timer', 'sleep for', 'wait for seconds'],
      intro: 'Here is a countdown timer that redraws one line instead of printing a new one each second.',
      code: function () {
        return String.raw`#!/usr/bin/env python3
"""A simple countdown timer."""

import sys
import time


def countdown(seconds):
    while seconds > 0:
        minutes, rest = divmod(seconds, 60)
        print(f"\r{minutes:02d}:{rest:02d}", end="", flush=True)
        time.sleep(1)
        seconds -= 1
    print("\r00:00")
    print("Done.")


def main():
    seconds = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    countdown(seconds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())`;
      }
    },
    {
      name: 'dice',
      keys: ['dice', 'roll', 'random number', 'pick a random', 'random choice'],
      intro: 'Here is a dice roller you can point at any number of dice and sides.',
      code: function () {
        return String.raw`#!/usr/bin/env python3
"""Roll dice."""

import random
import sys


def roll(count=2, sides=6):
    return [random.randint(1, sides) for _ in range(count)]


def main():
    count = int(sys.argv[1]) if len(sys.argv) > 1 else 2
    sides = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    values = roll(count, sides)
    print(f"{count}d{sides}: {values} = {sum(values)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())`;
      }
    },
    {
      name: 'backup',
      keys: ['backup', 'back up', 'copy files', 'archive files', 'save a copy'],
      intro: 'Here is a backup script that copies every file with a given extension into a timestamped folder.',
      code: function (ctx) {
        return String.raw`#!/usr/bin/env python3
"""Copy every file with a given extension into a backup folder."""

import argparse
import shutil
from datetime import datetime
from pathlib import Path


def backup(folder, extension, destination):
    source = Path(folder)
    target = Path(destination or f"backup-{datetime.now():%Y%m%d-%H%M%S}")
    target.mkdir(parents=True, exist_ok=True)
    copied = 0
    for path in sorted(source.glob(f"*{extension}")):
        if path.is_file():
            shutil.copy2(path, target / path.name)
            copied += 1
    return target, copied


def main():
    parser = argparse.ArgumentParser(description="Back up files by extension")
    parser.add_argument("folder", nargs="?", default="${ctx.folder || '.'}")
    parser.add_argument("-e", "--extension", default=".py")
    parser.add_argument("-d", "--destination")
    args = parser.parse_args()

    target, copied = backup(args.folder, args.extension, args.destination)
    print(f"copied {copied} files to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())`;
      }
    },
    {
      name: 'tidy folder',
      keys: ['organise', 'organize', 'by file type', 'by extension', 'sort my downloads', 'tidy', 'file type', 'messy folder', 'clean up my downloads'],
      intro: 'Here is a script that moves files into subfolders named after their type. It prints the plan first and only moves with --apply.',
      code: function (ctx) {
        return String.raw`#!/usr/bin/env python3
"""Tidy a folder: move each file into a subfolder named after its type."""

import argparse
import shutil
from pathlib import Path

GROUPS = {
    ".jpg": "images", ".jpeg": "images", ".png": "images", ".gif": "images", ".webp": "images",
    ".pdf": "documents", ".docx": "documents", ".txt": "documents", ".md": "documents",
    ".csv": "data", ".json": "data", ".xlsx": "data",
    ".mp3": "audio", ".wav": "audio", ".mp4": "video", ".mov": "video",
    ".zip": "archives", ".exe": "installers", ".msi": "installers",
}


def tidy(folder, apply):
    moved = 0
    for path in sorted(Path(folder).iterdir()):
        if not path.is_file():
            continue
        target = Path(folder) / GROUPS.get(path.suffix.lower(), "other")
        print(f"{path.name}  ->  {target.name}/")
        if apply:
            target.mkdir(exist_ok=True)
            shutil.move(str(path), target / path.name)
        moved += 1
    if not apply:
        print("\nDry run. Add --apply to move the files.")
    return moved


def main():
    parser = argparse.ArgumentParser(description="Tidy a folder by file type")
    parser.add_argument("folder", nargs="?", default="${ctx.folder || '.'}")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    print(f"{tidy(args.folder, args.apply)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())`;
      }
    }
  ];

  function genericProgram(request) {
    var description = String(request || 'a small task').replace(/["`]/g, '').replace(/\s+/g, ' ').slice(0, 90);
    return String.raw`#!/usr/bin/env python3
"""${description}"""

import argparse
from pathlib import Path


def run(path):
    """Do the work here."""
    # TODO: replace this with the real logic
    print(f"processing {path}")


def main():
    parser = argparse.ArgumentParser(description="${description}")
    parser.add_argument("path", nargs="?", default=".")
    args = parser.parse_args()
    run(Path(args.path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())`;
  }

  // How much of the query the record actually talks about. Rare words weigh
  // more, so an unseen word like "slack" pulls the score down and the app can
  // fall back to its starter template instead of an unrelated script.
  function termCoverage(index, record, query) {
    var wanted = [], seen = {};
    var terms = tokenize(query);
    for (var i = 0; i < terms.length; i++) {
      if (seen[terms[i]]) continue;
      seen[terms[i]] = true;
      wanted.push(terms[i]);
    }
    if (!wanted.length) return 1;
    var have = termSet(tokenize(searchText(record)));
    var total = 0, hit = 0;
    for (var j = 0; j < wanted.length; j++) {
      var term = wanted[j];
      var df = index && index.df ? (index.df.get(term) || 0) : 1;
      var weight = df ? Math.log(1 + index.records.length / df) : 6;
      total += weight;
      if (have.has(term)) hit += weight;
    }
    return total ? hit / total : 1;
  }

  function programAnswer(query) {
    if (!wantsProgram(query)) return null;
    var lower = String(query).toLowerCase();
    var ctx = {
      request: String(query).trim(),
      file: fileHint(query, ''),
      folder: '',
      column: columnHint(query, 'amount')
    };
    var best = null, bestScore = 0;
    for (var i = 0; i < RECIPES.length; i++) {
      var recipe = RECIPES[i], score = 0;
      for (var k = 0; k < recipe.keys.length; k++) {
        var key = recipe.keys[k];
        if (lower.indexOf(key) >= 0) score += key.split(' ').length + 1;
      }
      if (score > bestScore) { bestScore = score; best = recipe; }
    }
    var code = best ? best.code(ctx) : genericProgram(ctx.request);
    var intro = best ? best.intro : 'Here is a starting script — the work goes in run():';
    var note = best ? 'Run it with: python <file>.py' : 'Fill in run(), then run it with: python <file>.py';
    return {
      recipe: best ? best.name : 'starter',
      code: code,
      text: intro + '\n\n```python\n' + code.replace(/\s+$/, '') + '\n```\n\n' + note
    };
  }

  function estimateTokens(s) { return Math.ceil(String(s == null ? '' : s).length / 4); }

  function countTokens(records) {
    var total = 0;
    for (var i = 0; i < records.length; i++) total += tokenize(searchText(records[i])).length;
    return total;
  }

  return {
    VERSION: VERSION,
    tokenize: tokenize,
    stem: stem,
    searchText: searchText,
    indexText: indexText,
    label: label,
    body: body,
    recordKey: recordKey,
    parseRecord: parseRecord,
    parseFileContent: parseFileContent,
    parseText: parseText,
    chunkText: chunkText,
    merge: merge,
    buildIndex: buildIndex,
    search: search,
    retrievalAnswer: retrievalAnswer,
    wantsProgram: wantsProgram,
    programAnswer: programAnswer,
    termCoverage: termCoverage,
    systemPrompt: systemPrompt,
    estimateTokens: estimateTokens,
    countTokens: countTokens,
    firstLine: firstLine,
    slug: slug,
    extension: extension
  };
})();

if (typeof module !== 'undefined' && module.exports) module.exports = OnyxCore;

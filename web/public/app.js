/* ONYX browser app: Codex-style transcript, training, persistence, import/export. */
(function () {
  'use strict';

  var Core = window.OnyxCore;
  var KB_KEY = 'onyx.knowledge.v1';
  var CFG_KEY = 'onyx.config.v1';

  function $(selector) { return document.querySelector(selector); }

  var state = {
    records: [],
    manifest: { version: Core.VERSION, updated: '', records: 0, terms: 0, tokens: 0, trainings: 0, sources: [] },
    index: null,
    config: { model_url: '', model: '' },
    memoryOnly: false,
    storageWarned: false,
    history: [],
    historyIndex: 0,
    busy: false
  };

  /* ---------------------------------------------------------------- store ---- */

  function storageGet(key) {
    try {
      return window.localStorage.getItem(key);
    } catch (err) {
      state.memoryOnly = true;
      return null;
    }
  }

  function storageSet(key, value) {
    try {
      window.localStorage.setItem(key, value);
      return true;
    } catch (err) {
      state.memoryOnly = true;
      return false;
    }
  }

  function payload() {
    return {
      manifest: {
        version: Core.VERSION,
        updated: state.manifest.updated,
        records: state.records.length,
        terms: state.index ? state.index.terms : 0,
        tokens: state.manifest.tokens,
        trainings: state.manifest.trainings,
        sources: state.manifest.sources
      },
      records: state.records
    };
  }

  function kbBytes() {
    try {
      return new Blob([JSON.stringify(payload())]).size;
    } catch (err) {
      return JSON.stringify(payload()).length;
    }
  }

  function reindex() { state.index = Core.buildIndex(state.records); }

  function save() {
    state.manifest.tokens = Core.countTokens(state.records);
    var ok = storageSet(KB_KEY, JSON.stringify(payload()));
    if (!ok && !state.storageWarned) {
      state.storageWarned = true;
      line('warn', '! this browser blocked storage — knowledge stays in this tab only, use Export');
    }
    updateChrome();
    renderKnowledge();
  }

  function persistConfig() {
    var ok = storageSet(CFG_KEY, JSON.stringify(state.config));
    if (!ok) line('warn', '! this browser blocked storage — the model setting lasts for this tab only');
    updateChrome();
  }

  /* ------------------------------------------------------------- rendering ---- */

  function toBottom() {
    var scroll = $('#scroll');
    scroll.scrollTop = scroll.scrollHeight;
  }

  function line(kind, text) {
    var div = document.createElement('div');
    div.className = 'line' + (kind ? ' ' + kind : '');
    div.textContent = text;
    $('#scroll').appendChild(div);
    toBottom();
    return div;
  }

  function bubble(role, extra) {
    var wrap = document.createElement('div');
    wrap.className = 'msg ' + role + (extra ? ' ' + extra : '');
    var who = document.createElement('div');
    who.className = 'who';
    who.textContent = role === 'user' ? 'you' : 'onyx';
    var bodyEl = document.createElement('div');
    bodyEl.className = 'bubble';
    wrap.appendChild(who);
    wrap.appendChild(bodyEl);
    $('#scroll').appendChild(wrap);
    toBottom();
    return { wrap: wrap, body: bodyEl };
  }

  function appendUser(text) {
    bubble('user').body.textContent = text;
  }

  function codeBlock(code, lang) {
    var wrap = document.createElement('div');
    wrap.className = 'codewrap';
    var pre = document.createElement('pre');
    pre.className = 'code';
    var codeEl = document.createElement('code');
    codeEl.textContent = code;
    if (lang) codeEl.setAttribute('data-lang', lang);
    pre.appendChild(codeEl);
    wrap.appendChild(pre);
    var copy = document.createElement('button');
    copy.type = 'button';
    copy.className = 'copy';
    copy.textContent = 'copy';
    copy.addEventListener('click', function () {
      var done = function () {
        copy.textContent = 'copied';
        setTimeout(function () { copy.textContent = 'copy'; }, 1200);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(code).then(done, function () { copy.textContent = 'select it'; });
      } else {
        copy.textContent = 'select it';
      }
    });
    wrap.appendChild(copy);
    return wrap;
  }

  function renderRich(target, text) {
    var parts = String(text == null ? '' : text).split('```');
    for (var i = 0; i < parts.length; i++) {
      var chunk = parts[i];
      if (i % 2 === 1) {
        var lang = '';
        var nl = chunk.indexOf('\n');
        if (nl >= 0) {
          lang = chunk.slice(0, nl).trim();
          chunk = chunk.slice(nl + 1);
        } else {
          chunk = '';
        }
        if (chunk.trim()) target.appendChild(codeBlock(chunk.replace(/\s+$/, ''), lang));
      } else if (chunk.trim()) {
        var para = document.createElement('div');
        para.className = 'prose';
        para.textContent = chunk.replace(/^\n+/, '').replace(/\s+$/, '');
        target.appendChild(para);
      }
    }
  }

  function appendAnswer(text) {
    renderRich(bubble('assistant').body, text);
    toBottom();
  }

  /* --------------------------------------------------------------- helpers ---- */

  function plural(n, word) {
    if (n === 1) return '1 ' + word;
    return n + ' ' + (/y$/.test(word) ? word.slice(0, -1) + 'ies' : word + 's');
  }

  function formatNum(n) {
    try { return Number(n).toLocaleString('en-US'); }
    catch (err) { return String(n); }
  }

  function fmtBytes(n) {
    if (n < 1024) return n + ' B';
    var units = ['KB', 'MB', 'GB'];
    var value = n / 1024, index = 0;
    while (value >= 1024 && index < units.length - 1) { value /= 1024; index++; }
    return value.toFixed(1) + ' ' + units[index];
  }

  function modelEnabled() {
    return !!(state.config.model_url && state.config.model);
  }

  function modelLabel() {
    return modelEnabled() ? state.config.model + ' (local)' : 'knowledge-only (offline)';
  }

  function updateChrome() {
    $('#b-version').textContent = '(v' + Core.VERSION + ')';
    $('#b-model').textContent = modelLabel();
    $('#b-knowledge').textContent = state.records.length
      ? plural(state.records.length, 'record') + ' · ' + fmtBytes(kbBytes())
      : 'none yet — Train to teach it';
    $('#b-store').textContent = state.memoryOnly ? 'browser · this session only' : 'browser · localStorage';
    $('#train-status').textContent = state.records.length
      ? plural(state.records.length, 'record') + ' trained · saved in this browser'
      : 'Nothing trained yet.';
  }

  function renderKnowledge() {
    var summary = $('#kb-summary');
    var list = $('#kb-list');
    list.textContent = '';
    if (!state.records.length) {
      summary.textContent = 'Nothing trained yet.';
      return;
    }
    summary.textContent = [
      plural(state.records.length, 'record'),
      fmtBytes(kbBytes()),
      plural(state.index ? state.index.terms : 0, 'indexed term')
    ].join(' · ');
    state.records.slice(0, 40).forEach(function (rec) {
      var item = document.createElement('li');
      item.textContent = Core.label(rec);
      var bits = [];
      if (rec.tags && rec.tags.length) bits.push(rec.tags.join(', '));
      if (rec.source) bits.push(rec.source);
      if (bits.length) {
        var meta = document.createElement('span');
        meta.className = 'dim';
        meta.textContent = '  —  ' + bits.join(' · ');
        item.appendChild(meta);
      }
      list.appendChild(item);
    });
    if (state.records.length > 40) {
      var more = document.createElement('li');
      more.className = 'dim';
      more.textContent = '… and ' + plural(state.records.length - 40, 'more record');
      list.appendChild(more);
    }
  }

  function fillModelInputs() {
    $('#model-url').value = state.config.model_url || '';
    $('#model-name').value = state.config.model || '';
  }

  /* ---------------------------------------------------------------- model ----- */

  async function complete(query, hits) {
    var url = String(state.config.model_url).trim().replace(/\/+$/, '');
    if (url.slice(-17) !== '/chat/completions') url += '/chat/completions';
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, 180000);
    try {
      var response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        signal: controller.signal,
        body: JSON.stringify({
          model: state.config.model,
          messages: [
            { role: 'system', content: Core.systemPrompt(state.records, hits) },
            { role: 'user', content: query }
          ],
          temperature: 0.2,
          stream: false,
          max_tokens: 1200
        })
      });
      var text = await response.text();
      if (!response.ok) {
        throw new Error(response.status + ' ' + response.statusText + ': ' + text.slice(0, 160));
      }
      var data = JSON.parse(text);
      if (data.error && data.error.message) throw new Error(data.error.message);
      var choice = data.choices && data.choices[0] && data.choices[0].message;
      var answer = choice && choice.content;
      if (!answer) throw new Error('model returned an empty message');
      return String(answer).trim();
    } finally {
      clearTimeout(timer);
    }
  }

  async function generate(query) {
    var hits = Core.search(state.index, query, 5);
    if (modelEnabled()) {
      try {
        return { text: await complete(query, hits) };
      } catch (err) {
        console.warn('onyx: local model unavailable, answering from trained knowledge', err);
      }
    }
    var program = Core.programAnswer(query);
    if (program) return { text: program.text };
    return { text: Core.retrievalAnswer(hits) };
  }

  async function ask(text) {
    appendUser(text);
    setBusy(true);
    var pending = bubble('assistant', 'pending');
    pending.body.textContent = '…';
    try {
      var ans = await generate(text);
      pending.wrap.remove();
      appendAnswer(ans.text);
    } catch (err) {
      pending.wrap.remove();
      appendAnswer('Sorry — that one failed on my side. Ask me again?');
      console.warn('onyx: failed to answer', err);
    } finally {
      setBusy(false);
    }
  }

  /* -------------------------------------------------------------- training ---- */

  async function filesToBatch(files) {
    var batch = { records: [], sources: [], skipped: 0, warnings: [], files: 0 };
    for (var i = 0; i < files.length; i++) {
      var file = files[i];
      var text;
      try {
        text = await file.text();
      } catch (err) {
        batch.warnings.push(file.name + ': ' + String((err && err.message) || err));
        continue;
      }
      var result = Core.parseFileContent(file.name, text);
      batch.files++;
      batch.records = batch.records.concat(result.records);
      batch.skipped += result.skipped;
      for (var w = 0; w < result.warnings.length && batch.warnings.length < 5; w++) {
        batch.warnings.push(file.name + ': ' + result.warnings[w]);
      }
      batch.sources.push({ path: file.name, records: result.records.length, skipped: result.skipped });
    }
    return batch;
  }

  function mergeSources(existing, incoming) {
    var out = [], index = {};
    (existing || []).forEach(function (source) {
      index[source.path] = out.length;
      out.push(source);
    });
    incoming.forEach(function (source) {
      if (index[source.path] != null) {
        out[index[source.path]] = source;
        return;
      }
      index[source.path] = out.length;
      out.push(source);
    });
    return out;
  }

  function applyTraining(batch, replace) {
    if (!batch.records.length) {
      line('warn', '! no usable training records — the format is in basetrainer.txt');
      batch.warnings.forEach(function (warning) { line('warn', '! ' + warning); });
      return;
    }
    var merged = Core.merge(replace ? [] : state.records, batch.records);
    state.records = merged.records;
    state.manifest.trainings = (replace ? 0 : state.manifest.trainings) + 1;
    state.manifest.sources = mergeSources(state.manifest.sources, batch.sources);
    state.manifest.updated = new Date().toISOString();
    reindex();
    save();

    line('head', '› training');
    var details = ['parsed ' + plural(batch.records.length, 'record') + ' from ' + plural(batch.files, 'file')];
    if (batch.skipped) details.push('skipped ' + plural(batch.skipped, 'line') + ' that did not match the format');
    if (!replace && merged.dupes) details.push('skipped ' + plural(merged.dupes, 'record') + ' already trained');
    details.push('indexed ' + plural(state.index.terms, 'term') + ' · ' + formatNum(state.manifest.tokens) + ' tokens');
    details.push('saved in this browser (' + fmtBytes(kbBytes()) + ')');
    details.forEach(function (detail) { line('dim', '  · ' + detail); });
    batch.warnings.forEach(function (warning) { line('warn', '  ! ' + warning); });
    if (merged.added === 0 && !replace) {
      line('ok', '  ✓ knowledge unchanged — ' + plural(state.records.length, 'record') + ' available');
    } else {
      line('ok', '  ✓ ' + plural(merged.added, 'record') + ' trained — knowledge saved in this browser (' +
        formatNum(state.records.length) + ' total)');
    }
  }

  async function trainFromFiles(files, replace) {
    if (!files || !files.length) return;
    var batch = await filesToBatch(files);
    applyTraining(batch, replace);
  }

  function trainFromPaste() {
    var text = $('#paste').value.trim();
    if (!text) {
      line('warn', '! nothing pasted — paste JSONL records or choose files');
      return;
    }
    var result = Core.parseFileContent('pasted.jsonl', text);
    applyTraining({
      records: result.records,
      skipped: result.skipped,
      warnings: result.warnings,
      files: 1,
      sources: [{ path: 'pasted.jsonl', records: result.records.length, skipped: result.skipped }]
    }, $('#replace').checked);
    $('#paste').value = '';
  }

  function exportKnowledge() {
    if (!state.records.length) {
      line('warn', '! nothing to export yet — train a pack first');
      return;
    }
    var data = JSON.stringify(payload(), null, 2);
    var blob = new Blob([data], { type: 'application/json' });
    var url = URL.createObjectURL(blob);
    var link = document.createElement('a');
    link.href = url;
    link.download = 'onyx-knowledge.json';
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 1000);
    line('ok', '✓ exported ' + plural(state.records.length, 'record') + ' to onyx-knowledge.json');
  }

  function forgetAll() {
    if (!state.records.length) {
      line('dim', '  nothing trained yet');
      return;
    }
    if (!window.confirm('Delete all ' + plural(state.records.length, 'record') + ' trained in this browser?')) return;
    state.records = [];
    state.manifest = {
      version: Core.VERSION,
      updated: new Date().toISOString(),
      records: 0,
      terms: 0,
      tokens: 0,
      trainings: 0,
      sources: []
    };
    reindex();
    save();
    line('ok', '✓ knowledge cleared — nothing trained in this browser now');
  }

  /* ----------------------------------------------------------------- model ---- */

  function saveModel() {
    var url = $('#model-url').value.trim();
    var name = $('#model-name').value.trim();
    if (!url || !name) {
      line('warn', '! both the base URL and the model name are needed (or use Disable model)');
      return;
    }
    state.config.model_url = url;
    state.config.model = name;
    persistConfig();
    line('ok', '✓ model set to ' + name + ' at ' + url);
  }

  function clearModel() {
    state.config.model_url = '';
    state.config.model = '';
    persistConfig();
    fillModelInputs();
    line('ok', '✓ model disabled — answering from trained knowledge only');
  }

  /* -------------------------------------------------------------- commands ---- */

  function runCommand(text) {
    var parts = text.slice(1).split(/\s+/);
    var command = (parts.shift() || '').toLowerCase();
    switch (command) {
      case 'help':
      case '?':
        line('head', '› commands');
        [
          '/train            open the Train panel (files or pasted JSONL)',
          '/knowledge        what the app has learned',
          '/status           version, model and store details',
          '/model <url> <name>   point at a local OpenAI-compatible server',
          '/model off        answer from trained knowledge only',
          '/export           download onyx-knowledge.json',
          '/forget           delete everything trained in this browser',
          '/clear            clear the screen',
          '/exit             close the tab when you are done'
        ].forEach(function (row) { line('dim', '  ' + row); });
        break;
      case 'train':
        openDrawer('train');
        line('dim', '  · choose files, drop them here, or paste JSONL');
        break;
      case 'knowledge':
      case 'kb':
        openDrawer('knowledge');
        renderKnowledge();
        line('head', '› knowledge');
        if (!state.records.length) {
          line('dim', '  nothing trained yet — /train to teach it');
        } else {
          line('dim', '  ' + plural(state.records.length, 'record') + ' · ' + fmtBytes(kbBytes()) +
            ' · saved in this browser');
          state.manifest.sources.slice(0, 5).forEach(function (source) {
            line('dim', '  ' + source.path + ' — ' + plural(source.records, 'record'));
          });
        }
        break;
      case 'status':
        line('head', '› status');
        line('dim', '  version    ' + Core.VERSION);
        line('dim', '  model      ' + modelLabel());
        line('dim', '  endpoint   ' + (state.config.model_url || 'not configured'));
        line('dim', '  knowledge  ' + plural(state.records.length, 'record') + ' · ' + fmtBytes(kbBytes()));
        line('dim', '  store      ' + (state.memoryOnly ? 'browser (this session only)' : 'browser · localStorage'));
        if (state.manifest.updated) {
          line('dim', '  trained    ' + new Date(state.manifest.updated).toLocaleString() +
            ' · ' + plural(state.manifest.trainings, 'run'));
        }
        break;
      case 'model':
        var rest = parts.filter(function (part) { return part; });
        if (!rest.length) {
          openDrawer('model');
          line('dim', '  model:     ' + modelLabel());
          line('dim', '  endpoint:  ' + (state.config.model_url || 'none'));
          line('dim', '  set:       /model http://127.0.0.1:11434/v1 llama3.1:8b');
          line('dim', '  disable:   /model off');
        } else if (rest[0].toLowerCase() === 'off') {
          clearModel();
        } else if (rest.length >= 2) {
          state.config.model_url = rest[0];
          state.config.model = rest[1];
          persistConfig();
          fillModelInputs();
          line('ok', '✓ model set to ' + rest[1] + ' at ' + rest[0]);
        } else {
          line('error', '! usage: /model <base-url> <model-name>');
        }
        break;
      case 'export':
        exportKnowledge();
        break;
      case 'forget':
        forgetAll();
        break;
      case 'clear':
        $('#scroll').textContent = '';
        line('dim', 'v' + Core.VERSION + ' · ' + plural(state.records.length, 'record') + ' trained');
        break;
      case 'exit':
      case 'quit':
        line('dim', '  close the tab to leave ONYX');
        break;
      default:
        line('error', '! unknown command /' + command + ' — /help lists them');
    }
  }

  /* ------------------------------------------------------------------- ui ----- */

  function setBusy(busy) {
    state.busy = busy;
    $('#send').disabled = busy;
  }

  function openDrawer(panel) {
    $('#drawer').hidden = false;
    selectPanel(panel || 'train');
  }

  function closeDrawer() { $('#drawer').hidden = true; }

  function selectPanel(name) {
    ['train', 'knowledge', 'model'].forEach(function (key) {
      $('#panel-' + key).hidden = key !== name;
    });
    document.querySelectorAll('.tab').forEach(function (tab) {
      var active = tab.getAttribute('data-panel') === name;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    $('#drawer-title').textContent = name.charAt(0).toUpperCase() + name.slice(1);
    if (name === 'knowledge') renderKnowledge();
    if (name === 'model') fillModelInputs();
  }

  function autoGrow() {
    var input = $('#input');
    input.style.height = 'auto';
    var max = Math.floor(window.innerHeight * 0.4);
    input.style.height = Math.min(input.scrollHeight, max) + 'px';
  }

  function load() {
    var raw = storageGet(KB_KEY);
    if (raw) {
      try {
        var data = JSON.parse(raw);
        if (data && Array.isArray(data.records)) {
          state.records = data.records;
          if (data.manifest) {
            state.manifest = {
              version: data.manifest.version || Core.VERSION,
              updated: data.manifest.updated || '',
              records: data.records.length,
              terms: data.manifest.terms || 0,
              tokens: data.manifest.tokens || 0,
              trainings: data.manifest.trainings || 0,
              sources: Array.isArray(data.manifest.sources) ? data.manifest.sources : []
            };
          }
        }
      } catch (err) {
        line('warn', '! saved knowledge could not be read: ' + String((err && err.message) || err));
      }
    }
    var configRaw = storageGet(CFG_KEY);
    if (configRaw) {
      try {
        var config = JSON.parse(configRaw);
        state.config.model_url = config.model_url || '';
        state.config.model = config.model || '';
      } catch (err) { /* a bad config just means no model */ }
    }
    reindex();
    state.manifest.tokens = Core.countTokens(state.records);
  }

  function boot() {
    load();
    updateChrome();
    renderKnowledge();
    fillModelInputs();
    appendAnswer(state.records.length
      ? 'Hi — I\'m ONYX. I have ' + plural(state.records.length, 'record') +
        ' trained in this browser, so ask away. Type /help to see the commands, or ask me for a Python script.'
      : 'Hi — I\'m ONYX. I run entirely in this browser, so there is nothing to install and nothing to sign into. ' +
        'Ask me something, or open /train to teach me with a pack.');
    if (window.location.protocol === 'file:') {
      line('warn', '! opened from a file — some browsers limit storage here, so use Export to keep knowledge');
    }
    autoGrow();

    var input = $('#input');
    input.addEventListener('input', autoGrow);
    input.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        $('#composer').requestSubmit();
        return;
      }
      if (event.key === 'ArrowUp' && !input.value && state.history.length) {
        event.preventDefault();
        state.historyIndex = Math.max(0, state.historyIndex - 1);
        input.value = state.history[state.historyIndex] || '';
        autoGrow();
        return;
      }
      if (event.key === 'ArrowDown' && state.historyIndex < state.history.length) {
        event.preventDefault();
        state.historyIndex = Math.min(state.history.length, state.historyIndex + 1);
        input.value = state.history[state.historyIndex] || '';
        autoGrow();
      }
    });

    $('#composer').addEventListener('submit', async function (event) {
      event.preventDefault();
      if (state.busy) return;
      var text = input.value.trim();
      if (!text) return;
      input.value = '';
      autoGrow();
      if (state.history[state.history.length - 1] !== text) state.history.push(text);
      state.historyIndex = state.history.length;
      if (text.charAt(0) === '/') {
        runCommand(text);
        return;
      }
      await ask(text);
    });

    $('#btn-train').addEventListener('click', function () { openDrawer('train'); });
    $('#btn-knowledge').addEventListener('click', function () { openDrawer('knowledge'); });
    $('#btn-model').addEventListener('click', function () { openDrawer('model'); });
    $('#btn-export').addEventListener('click', exportKnowledge);
    $('#btn-export-2').addEventListener('click', exportKnowledge);
    $('#btn-import').addEventListener('click', function () { $('#import-input').click(); });
    $('#btn-forget').addEventListener('click', forgetAll);
    $('#btn-train-now').addEventListener('click', trainFromPaste);
    $('#btn-save-model').addEventListener('click', saveModel);
    $('#btn-clear-model').addEventListener('click', clearModel);
    $('#drawer-close').addEventListener('click', closeDrawer);
    document.querySelectorAll('.tab').forEach(function (tab) {
      tab.addEventListener('click', function () { selectPanel(tab.getAttribute('data-panel')); });
    });

    var drop = $('#drop');
    ['dragenter', 'dragover', 'drop'].forEach(function (type) {
      window.addEventListener(type, function (event) { event.preventDefault(); });
    });
    ['dragenter', 'dragover'].forEach(function (type) {
      drop.addEventListener(type, function () { drop.classList.add('over'); });
    });
    ['dragleave', 'dragend', 'drop'].forEach(function (type) {
      drop.addEventListener(type, function () { drop.classList.remove('over'); });
    });
    drop.addEventListener('drop', function (event) {
      var files = event.dataTransfer && event.dataTransfer.files;
      if (files && files.length) trainFromFiles(files, $('#replace').checked);
    });
    drop.addEventListener('click', function () { $('#file-input').click(); });
    drop.addEventListener('keydown', function (event) {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        $('#file-input').click();
      }
    });

    $('#file-input').addEventListener('change', function (event) {
      var files = event.target.files;
      trainFromFiles(files, $('#replace').checked);
      event.target.value = '';
    });
    $('#import-input').addEventListener('change', function (event) {
      trainFromFiles(event.target.files, false);
      event.target.value = '';
    });

    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && !$('#drawer').hidden) closeDrawer();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();

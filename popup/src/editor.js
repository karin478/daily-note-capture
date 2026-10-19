// The panel's editor: a whole daily (or yearly) note as plain markdown, rendered Obsidian-style, autosaved.
import { EditorState } from '@codemirror/state';
import { EditorView, Decoration, ViewPlugin, WidgetType, drawSelection, keymap, placeholder } from '@codemirror/view';
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands';
import { HighlightStyle, indentUnit, syntaxHighlighting } from '@codemirror/language';
import { autocompletion } from '@codemirror/autocomplete';
import { tags as t } from '@lezer/highlight';
import { deleteMarkupBackward } from '@codemirror/lang-markdown';
import { markdownExtension, newlineInList, previewRanges, toggleTask } from './preview.js';
import { clock, isoDay } from './timeline.js';
import { current, isYear, shift, title, yearOf } from './period.js';
import { afterSave } from './autosave.js';
import { tagCompletions, wikilinkCompletions } from './completion.js';
import { embedFor, htmlToMarkdown, isImage, linkOverSelection } from './paste.js';
import { stepZoom } from './zoom.js';
import { placeFor } from './place.js';
import { dayStep } from './keys.js';

const SAVE_DELAY = 400;
const MAX_ATTACHMENT = 50 * 1024 * 1024;
const post = (msg) => window.webkit?.messageHandlers?.note?.postMessage(msg);
const $ = (id) => document.getElementById(id);
const setStatus = (text) => { $('status').textContent = text; };

// Vault index from Hammerspoon: note names, file paths and tags.
let index = { vault: '', notes: [], files: {}, tags: [] };

const fileUrl = (path) => 'file://' + path.split('/').map(encodeURIComponent).join('/');
function resolveFile(target) {
  if (target.includes('/')) return index.vault && `${index.vault}/${target}`;
  return index.files[target] || null;
}

class Bullet extends WidgetType {
  eq() { return true; }
  toDOM() {
    const span = document.createElement('span');
    span.className = 'cm-bullet';
    span.textContent = '•';
    return span;
  }
}

class Checkbox extends WidgetType {
  constructor(from, checked) { super(); this.from = from; this.checked = checked; }
  eq(other) { return other.from === this.from && other.checked === this.checked; }
  toDOM(view) {
    const box = document.createElement('input');
    box.type = 'checkbox';
    box.className = 'cm-task';
    box.checked = this.checked;
    box.addEventListener('mousedown', (e) => {
      e.preventDefault();
      view.dispatch({ changes: toggleTask(view.state, this.from) });
    });
    return box;
  }
  ignoreEvent() { return false; }
}

// `![[file]]`: the picture for images, a clickable chip for anything else.
class Embed extends WidgetType {
  constructor(target, path) { super(); this.target = target; this.path = path; }
  eq(other) { return other.target === this.target && other.path === this.path; }
  toDOM() {
    if (this.path && isImage(this.target)) {
      const img = document.createElement('img');
      img.className = 'cm-embed-image';
      img.src = fileUrl(this.path);
      img.dataset.target = this.target;
      return img;
    }
    const chip = document.createElement('span');
    chip.className = 'cm-embed-file';
    chip.textContent = '📎 ' + this.target;
    chip.dataset.target = this.target;
    return chip;
  }
  ignoreEvent() { return false; }
}

function decorations(state) {
  const bullet = Decoration.replace({ widget: new Bullet() });
  const decos = previewRanges(state).map((r) => {
    switch (r.type) {
      case 'hide': return Decoration.replace({}).range(r.from, r.to);
      case 'bullet': return bullet.range(r.from, r.to);
      case 'task': return Decoration.replace({ widget: new Checkbox(r.from, r.checked) }).range(r.from, r.to);
      case 'embed': return Decoration.replace({ widget: new Embed(r.target, resolveFile(r.target)) }).range(r.from, r.to);
      case 'link': {
        const attributes = r.url ? { 'data-url': r.url } : { 'data-target': r.target };
        return Decoration.mark({ class: 'cm-wikilink', attributes }).range(r.from, r.to);
      }
      case 'highlight': return Decoration.mark({ class: 'cm-highlight' }).range(r.from, r.to);
      case 'time': return Decoration.mark({ class: 'cm-time' }).range(r.from, r.to);
      default: return Decoration.line({ class: r.cls }).range(r.from);
    }
  });
  return Decoration.set(decos, true);
}

const livePreview = ViewPlugin.fromClass(class {
  constructor(view) { this.decorations = decorations(view.state); }
  update(u) {
    if (u.docChanged || u.selectionSet || u.viewportChanged || u.transactions.some((tr) => tr.isUserEvent('index'))) {
      this.decorations = decorations(u.state);
    }
  }
}, { decorations: (v) => v.decorations });

const markdownStyle = HighlightStyle.define([
  { tag: t.heading1, fontSize: '1.6em', fontWeight: '700' },
  { tag: t.heading2, fontSize: '1.35em', fontWeight: '700' },
  { tag: t.heading3, fontSize: '1.15em', fontWeight: '600' },
  { tag: [t.heading4, t.heading5, t.heading6], fontWeight: '600' },
  { tag: t.strong, fontWeight: '700' },
  { tag: t.emphasis, fontStyle: 'italic' },
  { tag: t.strikethrough, textDecoration: 'line-through', color: 'var(--muted)' },
  { tag: t.monospace, fontFamily: 'var(--mono)', background: 'var(--code)', borderRadius: '4px' },
  { tag: [t.link, t.url], color: 'var(--accent)' },
  { tag: t.quote, color: 'var(--muted)' },
  { tag: t.processingInstruction, color: 'var(--muted)' },
]);

// Autosave: each change is saved after a short pause; one save in flight at a time.
let noteDate = null; // the note's key: YYYY-MM-DD, or YYYY for a year note
let base = '';
let timer = null;
let inflight = false;
let sent = null; // the body of the save in flight
let pending = null; // a note to switch to once the current one is saved: { date, create }

function requestSave(delay = SAVE_DELAY) {
  clearTimeout(timer);
  timer = setTimeout(flush, delay);
}

function flush() {
  clearTimeout(timer);
  const body = view.state.doc.toString();
  if (inflight || noteDate === null || body === base) return;
  inflight = true;
  sent = body;
  setStatus('保存中…');
  post({ action: 'save', date: noteDate, base, body });
}

function goToDay(day, create = false) {
  pending = { date: day, create };
  flush();
  if (!inflight && view.state.doc.toString() === base) {
    pending = null;
    post({ action: 'load', date: day, create });
  }
}
// Quick repeated steps add up: the header follows at once and only the day you stop on loads.
let wantedDay = null, stepTimer = null;
const shown = () => wantedDay ?? noteDate;
const stepDay = (delta) => () => {
  const from = shown();
  if (!from) return true;
  const day = (wantedDay = shift(from, delta));
  renderTitle(day);
  clearTimeout(stepTimer);
  stepTimer = setTimeout(() => goToDay(day), 150);
  return true;
};

const run = (fn) => (v) => { const tr = fn(v.state); if (tr) v.dispatch(tr); return !!tr; };

// ---- Links: click a rendered link (or ⌘-click any) to open it ----
function openLink(e, v) {
  const el = e.target.closest?.('[data-target], [data-url]');
  if (!el || e.button !== 0) return false;
  const embed = el.classList.contains('cm-embed-image') || el.classList.contains('cm-embed-file');
  const line = v.state.doc.lineAt(v.posAtDOM(el)).number;
  const onCursorLine = v.state.selection.ranges.some((r) => v.state.doc.lineAt(r.head).number === line);
  if (onCursorLine && !e.metaKey && !embed) return false;
  e.preventDefault();
  flush();
  post(el.dataset.url ? { action: 'open', url: el.dataset.url } : { action: 'open', target: el.dataset.target });
  return true;
}

// ---- Paste and drop, the way Obsidian handles them ----
let plainPaste = false; // ⌘⇧V pastes text as-is
const pendingAttachments = new Map();
let attachmentId = 0;

function attachFile(file, at) {
  if (file.size > MAX_ATTACHMENT) { setStatus(`${file.name} 超过 50MB，没有保存`); return; }
  const id = ++attachmentId;
  pendingAttachments.set(id, at);
  setStatus('保存附件中…');
  const reader = new FileReader();
  reader.onload = () => {
    const data = String(reader.result).split(',')[1] || '';
    const pasted = !file.name || /^image\.\w+$/.test(file.name);
    const ext = (file.type.split('/')[1] || 'png').replace('jpeg', 'jpg').replace(/\+.*/, '');
    post({ action: 'attach', id, name: pasted ? '' : file.name, ext, data });
  };
  reader.readAsDataURL(file);
}

function onPaste(e, v) {
  const data = e.clipboardData;
  if (!data) return false;
  const text = data.getData('text/plain');
  if (plainPaste) {
    plainPaste = false;
    v.dispatch(v.state.replaceSelection(text));
    return true;
  }
  const files = [...data.files];
  if (files.length) {
    for (const f of files) attachFile(f, v.state.selection.main.head);
    return true;
  }
  const link = linkOverSelection(v.state, text);
  if (link) { v.dispatch(link); return true; }
  const html = data.getData('text/html');
  if (html && !data.types.includes('vscode-editor-data')) {
    const md = htmlToMarkdown(html).trim();
    if (md) { v.dispatch(v.state.replaceSelection(md)); return true; }
  }
  return false;
}

function onDrop(e, v) {
  const files = [...(e.dataTransfer?.files || [])];
  if (!files.length) return false;
  e.preventDefault();
  const at = v.posAtCoords({ x: e.clientX, y: e.clientY }) ?? v.state.selection.main.head;
  for (const f of files) attachFile(f, at);
  return true;
}

const view = new EditorView({
  parent: $('editor'),
  state: EditorState.create({
    doc: '',
    extensions: [
      markdownExtension(),
      history(),
      drawSelection(), // WebKit's own caret isn't drawn in the borderless panel
      indentUnit.of('\t'),
      autocompletion({
        override: [
          (c) => wikilinkCompletions(c, index.notes, Object.keys(index.files)),
          (c) => tagCompletions(c, index.tags),
        ],
        icons: false,
      }),
      keymap.of([
        { key: 'Enter', run: run(newlineInList) },
        { key: 'Backspace', run: deleteMarkupBackward },
        { key: 'Mod-t', run: run((s) => s.update(s.replaceSelection(clock() + ' '))) },
        indentWithTab, ...defaultKeymap, ...historyKeymap,
      ]),
      syntaxHighlighting(markdownStyle),
      livePreview,
      EditorView.lineWrapping,
      placeholder('写点什么… 支持 markdown'),
      EditorView.updateListener.of((u) => { if (u.docChanged) requestSave(); }),
      EditorView.domEventHandlers({ mousedown: openLink, paste: onPaste, drop: onDrop }),
    ],
  }),
});

window.attached = ({ id, name, path }) => {
  const at = Math.min(pendingAttachments.get(id) ?? view.state.selection.main.head, view.state.doc.length);
  pendingAttachments.delete(id);
  index.files[name] = path;
  const line = view.state.doc.lineAt(at);
  const insert = (at > line.from && line.text.trim() ? '\n' : '') + embedFor(name);
  view.dispatch({ changes: { from: at, insert }, selection: { anchor: at + insert.length }, scrollIntoView: true });
};

// ---- Header: which note, and 日 / 年 ----
function renderTitle(day = noteDate) {
  const year = isYear(day);
  $('day').textContent = title(day);
  $('today').textContent = year ? '回到今年' : '回到今天';
  $('today').hidden = day === current(day);
  $('prev').title = year ? '前一年 ⌘[' : '前一天 ⌘[';
  $('next').title = year ? '后一年 ⌘]' : '后一天 ⌘]';
  for (const b of document.querySelectorAll('[data-mode]')) b.classList.toggle('on', (b.dataset.mode === 'year') === year);
}

// The header follows at once; a year note is created as soon as you open it.
function switchTo(key) {
  clearTimeout(stepTimer);
  wantedDay = key;
  renderTitle(key);
  goToDay(key, isYear(key));
}

let lastDay = null; // 日 brings you back to the day you left for the year
for (const b of document.querySelectorAll('[data-mode]')) {
  b.addEventListener('click', () => {
    const from = shown() ?? isoDay();
    if ((b.dataset.mode === 'year') === isYear(from)) return;
    if (isYear(from)) return switchTo(lastDay ?? isoDay());
    lastDay = from;
    switchTo(yearOf(from));
  });
}
$('prev').addEventListener('click', stepDay(-1));
$('next').addEventListener('click', stepDay(1));
$('today').addEventListener('click', () => switchTo(current(shown() ?? isoDay())));

// Each note's cursor and scroll, so reopening the panel or coming back to a note picks up there.
const places = new Map();
function rememberPlace() {
  if (noteDate === null) return;
  const { anchor, head } = view.state.selection.main;
  places.set(noteDate, { anchor, head, scrollTop: view.scrollDOM.scrollTop });
}

// ---- API called from Hammerspoon ----
window.loadNote = ({ date, body }) => {
  const editing = view.state.doc.toString() !== base;
  if (editing && date === noteDate) return; // keep unsaved typing; it saves against `base`
  rememberPlace();
  const place = placeFor(places.get(date), body.length);
  noteDate = date;
  wantedDay = null;
  base = body;
  view.dispatch({
    // an unchanged note is left as it is, so nothing on screen moves
    changes: body === view.state.doc.toString() ? [] : { from: 0, to: view.state.doc.length, insert: body },
    selection: { anchor: place.anchor, head: place.head },
    scrollIntoView: place.scrollTop === null, // the first time: at the end, ready to keep writing
  });
  if (place.scrollTop !== null) view.scrollDOM.scrollTop = place.scrollTop;
  clearTimeout(timer);
  renderTitle();
  setStatus('');
};

window.setIndex = (idx) => {
  index = idx;
  view.dispatch({ userEvent: 'index' }); // re-render embeds now that their files resolve
};

window.saved = ({ date, body }) => {
  inflight = false;
  if (date === noteDate) {
    const next = afterSave({ sent, stored: body, now: view.state.doc.toString() });
    base = next.base;
    setStatus(next.mismatch ? '文件里存下的内容和面板不一致，请在 Obsidian 里检查' : '已保存');
    if (next.again && !pending) return requestSave(0);
  }
  if (pending) goToDay(pending.date, pending.create); // goToDay saves anything typed meanwhile first
};

window.saveFailed = (message) => { inflight = false; setStatus('保存失败：' + message); };

window.conflict = (current) => {
  inflight = false;
  if (current.date !== noteDate) return;
  base = view.state.doc.toString(); // force the reload below
  window.loadNote(current);
  setStatus('日报在别处被改过，已刷新为最新内容');
};

window.flush = flush;
// Opening the panel shows today's note, or this year's if you left it on a year.
window.reopen = () => switchTo(current(shown() ?? isoDay()));
window.focusEditor = () => {
  view.focus();
  if (!view.hasFocus) setTimeout(() => view.focus(), 30);
};

// ---- Window behaviour ----

// A file dropped outside the editor would otherwise replace the page with that file.
for (const type of ['dragover', 'drop']) {
  window.addEventListener(type, (e) => { if (e.dataTransfer?.types.includes('Files')) e.preventDefault(); });
}

// The header and footer move the window, like a title bar; the edges resize it.
for (const handle of document.querySelectorAll('.head, .foot')) {
  handle.addEventListener('mousedown', (e) => {
    if (e.button === 0 && !e.target.closest('button')) { e.preventDefault(); post({ action: 'drag' }); }
  });
}
for (const grip of document.querySelectorAll('[data-edge]')) {
  grip.addEventListener('mousedown', (e) => {
    if (e.button === 0) { e.preventDefault(); post({ action: 'resize', edge: grip.dataset.edge }); }
  });
}

// ⌘= / ⌘- / ⌘0 zoom like a browser, flashing the new percentage; Hammerspoon remembers the level.
let zoom = 1, zoomTimer = null;
const applyZoom = (level) => {
  zoom = level;
  document.querySelector('.box').style.zoom = level;
};
window.setZoom = (level) => { if (level !== zoom) applyZoom(level); };
const ZOOM_KEYS = { Equal: 1, NumpadAdd: 1, Minus: -1, NumpadSubtract: -1, Digit0: 0, Numpad0: 0 };
function zoomKey(e) {
  const direction = ZOOM_KEYS[e.code];
  if (!e.metaKey || e.ctrlKey || e.altKey || direction === undefined) return false;
  e.preventDefault();
  e.stopPropagation();
  applyZoom(stepZoom(zoom, direction));
  post({ action: 'zoom', level: zoom });
  const badge = $('zoom');
  badge.textContent = `${Math.round(zoom * 100)}%`;
  badge.classList.add('show');
  clearTimeout(zoomTimer);
  zoomTimer = setTimeout(() => badge.classList.remove('show'), 1200);
  return true;
}

// Hammerspoon needs to know whether ⌃Space should close the panel or call it back.
window.addEventListener('focus', () => post({ action: 'focus', focused: true }));
window.addEventListener('blur', () => post({ action: 'focus', focused: false }));

document.addEventListener('keydown', (e) => {
  if (zoomKey(e)) return;
  const step = dayStep(e);
  if (step) {
    e.preventDefault();
    e.stopPropagation();
    stepDay(step)();
    return;
  }
  if (e.key === 'Escape' && !e.isComposing) {
    if (document.querySelector('.cm-tooltip-autocomplete')) return; // Esc closes the suggestions first
    e.preventDefault();
    flush();
    post({ action: 'hide' });
  }
  if (e.metaKey && e.shiftKey && e.key.toLowerCase() === 'v') plainPaste = true;
}, true);

window.__view = view;

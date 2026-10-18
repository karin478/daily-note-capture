// Pasting the way Obsidian does: web content as markdown, URLs over a selection as links,
// files as `![[embeds]]`.
import TurndownService from 'turndown';
import { gfm } from 'turndown-plugin-gfm';

const turndown = new TurndownService({
  headingStyle: 'atx',
  bulletListMarker: '-',
  codeBlockStyle: 'fenced',
  emDelimiter: '*',
  strongDelimiter: '**',
  hr: '---',
});
turndown.use(gfm);
turndown.remove(['style', 'script', 'meta', 'title']);
turndown.addRule('strikethrough', { filter: ['del', 's', 'strike'], replacement: (c) => `~~${c}~~` });
// "- item" with tab-indented children, as typed in Obsidian (Turndown's default is "-   item").
turndown.addRule('listItem', {
  filter: 'li',
  replacement(content, node, options) {
    content = content.replace(/^\n+/, '').replace(/\n+$/, '\n').replace(/\n/gm, '\n\t');
    let prefix = options.bulletListMarker + ' ';
    const list = node.parentNode;
    if (list.nodeName === 'OL') {
      const start = Number(list.getAttribute('start') || 1);
      prefix = `${start + Array.prototype.indexOf.call(list.children, node)}. `;
    }
    return prefix + content + (node.nextSibling && !/\n$/.test(content) ? '\n' : '');
  },
});

export const htmlToMarkdown = (html) => turndown.turndown(html);

const URL_ONLY = /^https?:\/\/\S+$/;

export function linkOverSelection(state, text) {
  const { main } = state.selection;
  const url = text.trim();
  if (state.selection.ranges.length > 1 || main.empty || !URL_ONLY.test(url)) return null;
  const label = state.sliceDoc(main.from, main.to);
  if (label.includes('\n')) return null;
  const insert = `[${label}](${url})`;
  return state.update({ changes: { from: main.from, to: main.to, insert }, selection: { anchor: main.from + insert.length }, userEvent: 'input.paste' });
}

const IMAGE = /\.(png|jpe?g|gif|bmp|svg|webp|avif)$/i;
export const isImage = (name) => IMAGE.test(name);
export const embedFor = (name) => `![[${name}]]`;

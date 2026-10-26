# daily-note-capture

在 macOS 上任何地方按一下 **⌃Space**，就弹出一个浮窗，直接编辑 Obsidian 里今天的日报，打完再按一下（或 Esc）就收起，自动保存。不用切到 Obsidian，也不用等它启动。

- 浮窗里就是那篇日报的完整 markdown 文件，改的就是 vault 里的原文件。
- 编辑体验接近 Obsidian 的实时预览：标题、粗体、列表、待办、`[[双链]]`、`#标签`、图片都会渲染。
- 日报放在哪个文件夹、用什么模板、文件名是什么日期格式，都自动读取 Obsidian 的「日记」核心插件设置（或 Periodic Notes 插件），不用手填。
- 也能写年报：点顶部的「年」，切到今年的年报，一年一篇。

安装请让你的 AI agent 照着 [INSTALL.md](INSTALL.md) 做，它会帮你找到 vault 和日报文件夹，并检查快捷键冲突。

## 使用

| 操作 | 按键 |
|---|---|
| 打开 / 收起浮窗 | **⌃Space**（可改，见下方「设置」） |
| 收起 | **Esc** |
| 前一天 / 后一天 | **⌘[** / **⌘]**（就是 P 右边那两个键；中文输入法下也能用），或点日期两边的 ‹ › |
| 日报 / 年报 | 点顶部的「日」「年」；年报模式下 ‹ ›、⌘[ ⌘] 换的是年份 |
| 回到今天 / 今年 | 点顶部的「回到今天」（年报模式下是「回到今年」） |
| 插入当前时间 | **⌘T** |
| 放大 / 缩小 / 恢复 | **⌘=** / **⌘-** / **⌘0** |

- **自动保存**：停下打字一会儿就存进文件，收起浮窗时也会存。
- **光标位置**：再打开浮窗、或切回看过的日子，光标和滚动位置都停在你上次离开的地方。第一次打开某篇时，光标在末尾。
- **还没有的日报**：切到还没有日报的那天时，显示的是模板内容；你打下第一个字时才会真正创建文件。
- **年报**：点「年」时，那一年的年报如果还没有，会马上建好。之后用 ‹ › 翻到别的年份，只看不写的话不会建文件。点「日」回到你原来那一天。收起浮窗时停在年报上，下次打开显示的是今年的年报。
- **别处也改了同一篇**：如果你在 Obsidian 或别的设备上也改了这篇日报，浮窗会提示「日报在别处被改过」，并刷新成文件里的最新内容。
- **链接和标签**：输入 `[[` 会补全笔记名，输入 `#` 会补全标签；点链接会在 Obsidian 里打开。
- **粘贴和拖入**：可以粘贴或拖入图片、文件，它们会存到 Obsidian 设置的附件位置；从网页复制的内容会转成 markdown。
- **窗口**：拖顶栏或底栏移动，拖边缘调大小；会记住位置和大小。浮窗出现在你正在用的那块屏幕上。
- **命令行追加**：`.venv/bin/python capture.py "一句话"` 会把这句话加到今天日报的末尾。

## 设置

大多数人不需要设置。想改的话，写在 `~/.config/daily-note-capture/config.json` 里，每一项都可以省略：

```json
{
  "vault": "/Users/you/Documents/MyVault",
  "folder": "Journal/Daily",
  "template": "Templates/Daily",
  "format": "YYYY-MM-DD",
  "year_folder": "Journal/Yearly",
  "hotkey": "ctrl+space"
}
```

| 键 | 作用 | 不写时 |
|---|---|---|
| `vault` | vault 文件夹的完整路径 | Obsidian 只登记了一个 vault 时自动用它；有多个时必须写 |
| `folder` | 日报文件夹，相对 vault | 读 Obsidian「日记」设置里的「新文件存放位置」 |
| `template` | 模板文件，相对 vault，`.md` 可省略 | 读「日记」设置里的「模板文件位置」 |
| `format` | 文件名的日期格式，支持 `YYYY YY MM M DD D`、`/` 分子文件夹、`[文字]` | 读「日记」设置里的「日期格式」，再没有就用 `YYYY-MM-DD` |
| `year_folder` | 年报文件夹，相对 vault | 开了 Periodic Notes 的 Yearly 时读它的设置（文件夹留空就是 vault 根目录）；没开就和日报放在一起 |
| `year_template` | 年报模板 | 读 Periodic Notes Yearly 的模板，没有就是空白 |
| `year_format` | 年报文件名格式 | 读 Periodic Notes Yearly 的格式，再没有就用 `YYYY`，即 `2026.md` |
| `hotkey` | 浮窗快捷键，如 `cmd+shift+n`、`⌥Space` | `ctrl+space` |

模板里的 `{{date}}`、`{{date:YYYY年M月D日}}`、`{{title}}` 会被填上；Templater 的 `<% %>` 语法不支持，会原样保留。

改了设置之后，运行 `.venv/bin/python capture.py --doctor` 确认读到的路径，再在 Hammerspoon 菜单里选 **Reload Config**。

## 书模式（可选）

给读书用的：在浮窗里搜任何一本书，点一下，浮窗就变成这本书的笔记，边读边写（或者开着语音输入一直说）。配置里有 `books` 一段时，顶部才会多出「书」按钮。

```json
{
  "books": {
    "folder": "Reading/Books",
    "sources": [
      { "path": "Reading/data/douban-read.json", "kind": "douban", "label": "读过" },
      { "path": "Reading/data/douban-wish.json", "kind": "douban", "label": "想读" },
      { "path": "Reading/data/weread.json", "kind": "weread", "label": "微信读书" }
    ],
    "template": "Templates/Book"
  }
}
```

| 键 | 作用 | 不写时 |
|---|---|---|
| `folder` | 书籍笔记放在哪个文件夹，相对 vault（必填） | — |
| `sources` | 书单文件，相对 vault 或绝对路径。`kind` 是 `douban`（字段 `douban_id title author cover_url wish_date`）或 `weread`（字段 `bookId title author cover lastReadUpdate`）。同一本书在几个书单里都有时，排在前面的书单优先 | 没有书单，只有已有的书籍笔记和豆瓣搜索 |
| `template` | 新书笔记的模板 | 一个简单的模板：书名、作者、封面、豆瓣链接，加上下面的段落 |
| `section` | 写想法的那一段的标题 | `边读边想` |
| `cover_folder` | 封面存在书籍文件夹下的哪个子文件夹 | `封面` |
| `douban_search` | 搜索时要不要同时搜豆瓣 | `true` |

模板里可以用 `{{title}}`、`{{author}}`、`{{cover}}`、`{{douban_id}}`、`{{douban_url}}`、`{{section}}`、`{{date}}`。

- 在 frontmatter 里，它们会被填成可以直接用的值：需要时自动加引号，没有值时是 `null`。所以模板里**不要自己加引号**，写 `title: {{title}}`、`cover: {{cover}}` 就行。
- 在正文里，`{{title}}` 和 `{{author}}` 是原样的文字，没有作者时是空的。

- **书架**：最上面是打开过的书，最近的在前；下面是所有书。封面边滚动边下载，缓存在 `~/Library/Caches/daily-note-capture/covers/`。
- **搜索**：按书名、作者和笔记里的字搜，打开过的书排在前面。停下打字一会儿，下面会出现「豆瓣搜索」，书单里没有的书也能搜到、能打开。回车打开第一本。
- **同一本书**：书名和作者都相同就算同一本书，不同版本合成一本。
- **打开一本书**：浮窗变成这本书的笔记，光标停在「边读边想」里今天的日期下面。今天第一次打开时，日期会自动加上去。
- **没写字不建文件**：还没有笔记的书，打开后显示的是模板；打下第一个字时才会真正建文件，同时把封面复制进 vault。只看不写的话，什么文件都不会留下。
- 顶部的「← 书架」回到书架，「在 Obsidian 打开」在 Obsidian 里打开这篇笔记（笔记建好之后才会出现）。

## 开发

- 结构：
  - `hammerspoon/`：窗口和快捷键（Lua）。
  - `popup/src/`：编辑器（CodeMirror 6）。
  - `capture.py`、`settings.py`、`vault.py`：读写日报（只用 Python 标准库）。
  - `books.py`：书模式的书目、书籍笔记、封面和豆瓣搜索。
- 改了 `popup/src/` 之后要运行 `npm install && npm run build`。打包好的 `popup/editor.bundle.js` 已经提交在仓库里，所以只是使用的话不需要 Node。
- 测试：`.venv/bin/python -m pip install pytest && .venv/bin/python -m pytest`，`npm run test:js`，`npm run test:lua`（需要 `luajit`）。

## License

MIT

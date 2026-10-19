# 安装说明（给 AI agent）

你在帮用户在 macOS 上装 daily-note-capture：按一下快捷键弹出浮窗，编辑 Obsidian 里今天的日报。请按顺序做，**每一步都用给出的命令检查过再往下走**。

有两条规则：

- **日报在哪，不要猜。** 自动检测找不到，或者找到的不止一个时，直接问用户 vault 和日报文件夹在哪里。检测到了也要把结果给用户看一眼，让对方确认。
- **会弹出系统窗口、或要改用户已有配置的步骤，先告诉用户。**

## 0. 前提

- macOS，并且装了 Obsidian，有一个放日报的 vault。
- 有 `python3`，版本 3.9 或以上：

  ```sh
  python3 --version
  ```

  在没装过开发者工具的 Mac 上，这条命令本身就会弹出「安装命令行开发者工具」的系统窗口，所以**运行前先告诉用户**，请对方点「安装」，装完再继续。

## 1. 安装 Hammerspoon

Hammerspoon 是免费开源的 macOS 自动化工具，浮窗和快捷键都靠它。

```sh
ls /Applications/Hammerspoon.app || brew install --cask hammerspoon
```

没有 Homebrew 的话，让用户去 <https://www.hammerspoon.org> 下载，把它拖进「应用程序」。

装好后打开一次：`open -a Hammerspoon`。第一次打开会出现它的偏好设置窗口，**先告诉用户**会弹窗：

- 请用户勾选 **Launch Hammerspoon at login**，这样开机后快捷键就能直接用。
- 这个工具**不需要**「辅助功能」权限。如果 Hammerspoon 请求这个权限，可以跳过。

## 2. 下载代码

放在哪都可以，常见的是 `~/dev`：

```sh
git clone <这个仓库的地址> ~/dev/daily-note-capture
cd ~/dev/daily-note-capture
python3 -m venv .venv
```

不需要装任何 Python 包，也不需要 Node：编辑器已经打包好放在仓库里了。

## 3. 找到 vault 和日报文件夹

```sh
.venv/bin/python capture.py --doctor
```

**情况一：成功。** 会打印 vault、日报文件夹、模板、日期格式、今天日报和今年年报的路径。

- 把这几行给用户看，问「这是你放日报的地方吗？」。
- 同时用 `ls` 看看日报文件夹里是不是已经有用户的日报，文件名格式对不对得上。
- 年报的位置也给用户看一下。用户已经有放年报的文件夹的话，在配置里写上 `"year_folder"`（见下方）。
- 用户确认了就进入第 4 步。

**情况二：报错。** 比如「找不到 Obsidian vault」，或者「Obsidian 里有多个 vault」。

- 问用户：日报在哪个 vault？放在 vault 里的哪个文件夹？
- 报错里如果列出了几个 vault，可以列给用户挑。

**情况三：成功了，但路径不对。** 比如用户的日报不是用 Obsidian「日记」核心插件建的，而是用别的插件或手动建的。

- 问用户日报放在哪个文件夹、文件名长什么样、有没有模板。

情况二、三问清楚之后，写进配置文件。只写需要的项：

```sh
mkdir -p ~/.config/daily-note-capture
cat > ~/.config/daily-note-capture/config.json <<'EOF'
{
  "vault": "/vault 的完整路径",
  "folder": "日报文件夹，相对 vault",
  "template": "模板，相对 vault，可省略",
  "format": "YYYY-MM-DD"
}
EOF
```

- 写完再运行一次 `--doctor`，直到打印出的路径和用户说的一致。
- `format` 只支持 `YYYY YY MM M DD D`、`/`、`[文字]`。如果用户的文件名里有星期几或英文月份，`--doctor` 会报错。这时要告诉用户：这种格式暂时不支持。

## 4. 检查快捷键冲突

默认快捷键是 **⌃Space**。macOS 默认也用 ⌃Space 切换输入法，有中文等多个输入法的用户很容易冲突。

先查系统的输入法快捷键有没有开：

```sh
/usr/libexec/PlistBuddy -c "Print :AppleSymbolicHotKeys:60:enabled" ~/Library/Preferences/com.apple.symbolichotkeys.plist
```

- 输出 `false`：没有冲突。
- 输出 `true`，或者报 `Does Not Exist`（表示沿用系统默认，默认是开着的）：有冲突。告诉用户，然后请对方二选一：
  - **保留 ⌃Space 给浮窗**：请用户自己去 系统设置 → 键盘 → 键盘快捷键… → 输入法，关掉「选择上一个输入法」，或者给它换一个键。
  - **给浮窗换一个键**：在 `config.json` 里加上 `"hotkey": "cmd+shift+space"`，用用户选的键。

## 5. 接入 Hammerspoon

把下面两行**追加**到 `~/.hammerspoon/init.lua` 的末尾，路径换成第 2 步实际放代码的绝对路径。这个文件如果已经有内容，**不要覆盖**；改之前先告诉用户你要改它。

```lua
package.path = "/Users/<用户名>/dev/daily-note-capture/hammerspoon/?.lua;" .. package.path
require("note_popup").start()
```

然后重启 Hammerspoon，让配置生效：

```sh
killall Hammerspoon; sleep 1; open -a Hammerspoon
```

## 6. 验证

1. 请用户按一下快捷键，应该弹出浮窗，显示今天的日报。今天还没有日报的话，显示的是模板内容。
2. 请用户在浮窗里随便打一个词，停一秒后按 Esc 收起。
3. 你用 `cat` 看第 3 步 `--doctor` 打印的「今天的日报」路径，确认那个词已经写进文件。
4. 最后请用户在浮窗里把这个词删掉。

## 出问题时

| 现象 | 怎么办 |
|---|---|
| 弹出「读取日报失败」 | 运行 `--doctor`，按它的报错处理 |
| 按快捷键没反应 | 先确认 Hammerspoon 在运行（菜单栏有它的图标）。点图标 → **Console**，看有没有红色报错，常见原因是 `init.lua` 里的路径写错。再按第 4 步排查快捷键冲突 |
| 浮窗打开了，但一片空白 | 运行 `ls popup/editor.bundle.js`，确认文件存在 |
| 想换快捷键或日报位置 | 改 `~/.config/daily-note-capture/config.json`，然后在 Hammerspoon 菜单里点 **Reload Config** |

## 卸载

1. 删掉 `~/.hammerspoon/init.lua` 里加的那两行。
2. 删掉代码文件夹和 `~/.config/daily-note-capture/`。
3. 日报文件本身不受影响。

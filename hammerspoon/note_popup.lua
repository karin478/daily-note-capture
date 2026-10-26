-- Floating note panel: edits a whole daily note in place, autosaved.
-- The webview is created once and only shown/hidden; file reads and writes run as background
-- tasks so the hotkey never waits on them.
local M = {}

local HOME = os.getenv("HOME")
-- The repo this file sits in, wherever it was cloned.
local ROOT = debug.getinfo(1, "S").source:match("^@(.*)/hammerspoon/[^/]*$")
local CONFIG = HOME .. "/.config/daily-note-capture/config.json"
local PYTHON = ROOT .. "/.venv/bin/python"
local SCRIPT = ROOT .. "/capture.py"
local PAGE = "file://" .. ROOT:gsub(" ", "%%20") .. "/popup/index.html"
local WIDTH, HEIGHT = 560, 680
local MIN_W, MIN_H = 360, 260
local FRAME_KEY = "notePopup.frame"
local ZOOM_KEY = "notePopup.zoom"
local CACHE = HOME .. "/Library/Caches/daily-note-capture"
local INDEX_FILE = CACHE .. "/index.json"
local BOOKS_FILE = CACHE .. "/books.json"
local RECENT_KEY = "notePopup.recentBooks"
local MAX_RECENT = 200

local panel, previousApp, mouseTimer, index, indexData, indexedAt, booksData, booksAt
local visible, focused = false, false
local placement = require("placement")
local hotkey = require("hotkey")

local function js(fn, arg)
  panel:evaluateJavaScript(string.format("%s(%s)", fn, arg or ""))
end

local function run(args, callback, input)
  local task = hs.task.new(PYTHON, function(code, out, err) callback(code, out, err) end, args)
  if input then task:setInput(input) end
  task:start()
end

-- `day` is YYYY-MM-DD, or YYYY for a year note; `create` makes the note now instead of on first save.
local function load(day, create)
  run({ SCRIPT, "--get", day, create and "--create" or nil }, function(code, out, err)
    if code == 0 then
      js("loadNote", out)
      js("setZoom", tostring(hs.settings.get(ZOOM_KEY) or 1))
    else hs.alert.show("✗ 读取日报失败：" .. (err or ""), 5) end
  end)
end

-- The page always gets the last index right away; it is rebuilt at most once a minute.
local function refreshIndex()
  if indexData then js("setIndex", indexData) end
  if indexedAt and os.time() - indexedAt < 60 then return end
  indexedAt = os.time()
  -- The index (hundreds of KB) goes through a file; hs.task pipes don't carry that much intact.
  run({ SCRIPT, "--index", INDEX_FILE }, function(code)
    local f = code == 0 and io.open(INDEX_FILE, "r")
    if not f then return end
    local data = f:read("a")
    f:close()
    local decoded = hs.json.decode(data)
    if decoded then
      index, indexData = decoded, data
      js("setIndex", data)
    end
  end)
end

-- 书 mode: the catalog, like the index, comes from the last build at once and is rebuilt at most once a
-- minute. Without a books section in the config --books fails and the 书 button stays hidden.
local function readFile(path, remove)
  local f = io.open(path, "r")
  if not f then return nil end
  local data = f:read("a")
  f:close()
  if remove then os.remove(path) end
  return data
end

local function sendRecents()
  js("setRecents", hs.json.encode(hs.settings.get(RECENT_KEY) or {}))
end

local function refreshBooks()
  if booksData then
    js("setBooks", booksData)
    sendRecents()
  end
  if booksAt and os.time() - booksAt < 60 then return end
  booksAt = os.time()
  run({ SCRIPT, "--books", BOOKS_FILE }, function(code)
    local data = code == 0 and readFile(BOOKS_FILE)
    if data then
      booksData = data
      js("setBooks", data)
      sendRecents()
    end
  end)
end

-- When each book was last opened; only the latest MAX_RECENT are kept.
local function remember(key)
  local recent = hs.settings.get(RECENT_KEY) or {}
  recent[key] = os.time()
  local keys = {}
  for k in pairs(recent) do keys[#keys + 1] = k end
  if #keys > MAX_RECENT then
    table.sort(keys, function(a, b) return recent[a] > recent[b] end)
    for i = MAX_RECENT + 1, #keys do recent[keys[i]] = nil end
  end
  hs.settings.set(RECENT_KEY, recent)
end

local function openBook(msg)
  local book = msg.book or {}
  if book.key then remember(book.key) end
  run({ SCRIPT, "--book-open" }, function(code, out, err)
    if code == 0 then js("loadBook", out)
    else hs.alert.show("✗ 打开书失败：" .. (err or ""), 5) end
  end, hs.json.encode(book))
end

local function covers(msg)
  local file = string.format("%s/covers-%d-%d.json", CACHE, os.time(), math.random(1000000))
  run({ SCRIPT, "--covers", file }, function(code)
    js("coversLoaded", code == 0 and readFile(file, true) or "{}")
  end, hs.json.encode(msg.items or {}))
end

local function doubanSearch(msg)
  run({ SCRIPT, "--douban-search", msg.q or "" }, function(code, out)
    js("doubanResults", code == 0 and out or hs.json.encode({ q = msg.q, error = true }))
  end)
end

local function save(msg)
  -- a book's note names its cover to copy in, until the copy is made
  run({ SCRIPT, "--set", msg.date, msg.base, msg.body, msg.coverSrc, msg.coverRel }, function(code, out, err)
    if code == 0 then
      js("saved", out)
    elseif code == 3 then
      js("conflict", out)
    else
      js("saveFailed", hs.json.encode({ err or "" }):sub(2, -2))
    end
  end)
end

local function attach(msg)
  run({ SCRIPT, "--attach", msg.name or "", msg.ext or "png" }, function(code, out, err)
    if code == 0 then
      local saved = hs.json.decode(out)
      saved.id = msg.id
      js("attached", hs.json.encode(saved))
    else
      js("saveFailed", hs.json.encode({ "附件保存失败 " .. (err or "") }):sub(2, -2))
    end
  end, msg.data)
end

---------------------------------------------------------------------------------------------
-- Window: show/hide, drag, resize, open links.

local function hide(returnFocus)
  if not visible then return end
  visible, focused = false, false
  js("flush")
  panel:hide()
  -- _activate skips activate()'s Accessibility lookups, which stall for seconds without that permission
  if returnFocus ~= false and previousApp then previousApp:_activate(false) end
end

local function focusPanel()
  hs.focus() -- no panel:hswindow() here: it walks every window on screen and costs ~1.6s
  js("focusEditor")
end

local function rect(f) return { x = f.x, y = f.y, w = f.w, h = f.h } end

-- The size and spot you last left it at, carried over to `screen`.
local function frameOn(screen)
  local screens = {}
  for _, s in ipairs(hs.screen.allScreens()) do screens[#screens + 1] = rect(s:frame()) end
  local f = placement.place(hs.settings.get(FRAME_KEY), screens, rect(screen:frame()), { w = WIDTH, h = HEIGHT })
  return hs.geometry.rect(f.x, f.y, f.w, f.h)
end

-- mainScreen is the screen holding the focused window, so ask before the panel takes focus.
local function moveToWorkingScreen()
  local screen = hs.screen.mainScreen()
  if not hs.geometry(panel:frame()).center:inside(screen:frame()) then panel:frame(frameOn(screen)) end
end

local function show()
  previousApp = hs.application.frontmostApplication()
  panel:frame(frameOn(hs.screen.mainScreen()))
  visible = true
  panel:show()
  focusPanel()
  js("reopen") -- the page asks for today's note, or this year's, or the book or shelf it was on
  refreshIndex()
  refreshBooks()
end

local function saveFrame()
  local f = panel:frame()
  hs.settings.set(FRAME_KEY, { x = f.x, y = f.y, w = f.w, h = f.h })
end

-- Follow the mouse until the left button is released. Polling avoids hs.eventtap, which
-- needs Accessibility permission.
local function followMouse(apply)
  if mouseTimer then mouseTimer:stop() end
  local start, origin = hs.mouse.absolutePosition(), panel:frame()
  mouseTimer = hs.timer.doEvery(1 / 120, function()
    local mouse = hs.mouse.absolutePosition()
    apply(origin, mouse.x - start.x, mouse.y - start.y)
    if not hs.mouse.getButtons().left then
      mouseTimer:stop()
      mouseTimer = nil
      saveFrame()
    end
  end)
end

local function drag()
  followMouse(function(o, dx, dy) panel:topLeft({ x = o.x + dx, y = o.y + dy }) end)
end

local function resize(edge)
  followMouse(function(o, dx, dy)
    local x, w, h = o.x, o.w, o.h
    if edge:find("r") then w = math.max(MIN_W, o.w + dx) end
    if edge:find("b") then h = math.max(MIN_H, o.h + dy) end
    if edge:find("l") then
      w = math.max(MIN_W, o.w - dx)
      x = o.x + o.w - w
    end
    panel:frame({ x = x, y = o.y, w = w, h = h })
  end)
end

local function open(msg)
  local url = msg.url
  if not url and msg.target and index then
    url = "obsidian://open?vault=" .. hs.http.encodeForQuery(index.vaultName) .. "&file=" .. hs.http.encodeForQuery(msg.target)
  end
  if url then
    hide(false)
    hs.urlevent.openURL(url)
  end
end

local handlers = {
  save = save,
  hide = function() hide() end,
  drag = drag,
  resize = function(msg) resize(msg.edge or "rb") end,
  load = function(msg) load(msg.date, msg.create) end,
  attach = attach,
  open = open,
  openBook = openBook,
  covers = covers,
  doubanSearch = doubanSearch,
  zoom = function(msg) hs.settings.set(ZOOM_KEY, msg.level) end,
  focus = function(msg) focused = msg.focused and visible end,
}

local function create()
  local controller = hs.webview.usercontent.new("note")
  controller:setCallback(function(msg)
    local body = msg.body or {}
    local handler = handlers[body.action]
    if handler then handler(body) end
  end)
  panel = hs.webview.new(frameOn(hs.screen.mainScreen()), {}, controller)
    :windowStyle({ "borderless" })
    :transparent(true)
    :shadow(true)
    :allowTextEntry(true)
    :level(hs.drawing.windowLevels.floating)
    :closeOnEscape(false)
    :deleteOnClose(false)
    :url(PAGE)
end

-- Hidden: open it. Open but you are working elsewhere: bring it to that screen. In use: close it.
function M.toggle()
  if not visible then
    show()
  elseif not focused then
    previousApp = hs.application.frontmostApplication()
    moveToWorkingScreen()
    focusPanel()
  else
    hide()
  end
end

-- With no arguments the shortcut comes from "hotkey" in the config file, else ctrl+space.
function M.start(mods, key)
  if not mods then
    local shortcut = hotkey.parse((hs.json.read(CONFIG) or {}).hotkey)
    mods, key = shortcut.mods, shortcut.key
  end
  create()
  M.hotkey = hs.hotkey.bind(mods, key, M.toggle)
end

M._panel = function() return panel end

return M

-- Run with `npm run test:lua` (plain Lua; no Hammerspoon needed).
package.path = "hammerspoon/?.lua;" .. package.path
local parse = require("hotkey").parse

local failures, passed = 0, 0
local function test(name, fn)
  local ok, err = pcall(fn)
  if ok then passed = passed + 1 else failures = failures + 1; print("FAIL " .. name .. "\n  " .. err) end
end
local function same(got, mods, key)
  local a, b = table.concat(got.mods, ","), table.concat(mods, ",")
  if a ~= b or got.key ~= key then
    error(string.format("got %s+%s, want %s+%s", a, tostring(got.key), b, key), 2)
  end
end

test("nothing set is ctrl+space", function() same(parse(nil), { "ctrl" }, "space") end)
test("a written shortcut is split into modifiers and key", function()
  same(parse("cmd+shift+n"), { "cmd", "shift" }, "n")
end)
test("long names, symbols and any case are accepted", function()
  same(parse("Control+Option+Space"), { "ctrl", "alt" }, "space")
  same(parse("⌘⇧K"), { "cmd", "shift" }, "k")
end)
test("a shortcut with no key falls back to ctrl+space", function() same(parse("cmd+"), { "ctrl" }, "space") end)

print(string.format("%d passed, %d failed", passed, failures))
os.exit(failures == 0 and 0 or 1)

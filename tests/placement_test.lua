-- Run with `npm run test:lua` (plain Lua; no Hammerspoon needed).
package.path = "hammerspoon/?.lua;" .. package.path
local place = require("placement").place

local failures, passed = 0, 0
local function test(name, fn)
  local ok, err = pcall(fn)
  if ok then passed = passed + 1 else failures = failures + 1; print("FAIL " .. name .. "\n  " .. err) end
end
local function same(a, b)
  for _, k in ipairs({ "x", "y", "w", "h" }) do
    if math.abs(a[k] - b[k]) > 0.5 then
      error(string.format("%s: got %s, want %s", k, a[k], b[k]), 2)
    end
  end
end

local laptop = { x = 0, y = 33, w = 1728, h = 1084 }
local wide = { x = -2957, y = -1410, w = 3440, h = 1350 }
local screens = { laptop, wide }
local SIZE = { w = 560, h = 680 }

test("with nothing saved it is centred on the target screen", function()
  same(place(nil, screens, wide, SIZE), { x = -2957 + 1440, y = -1410 + 335, w = 560, h = 680 })
end)

test("a frame saved on the target screen is kept as is", function()
  local saved = { x = 100, y = 200, w = 600, h = 500 }
  same(place(saved, screens, laptop, SIZE), saved)
end)

test("on another screen it keeps its size and its relative spot", function()
  -- flush with the laptop's right edge and top → flush with the wide screen's right edge and top
  local saved = { x = 1728 - 600, y = 33, w = 600, h = 500 }
  same(place(saved, screens, wide, SIZE), { x = -2957 + 3440 - 600, y = -1410, w = 600, h = 500 })
end)

test("a frame larger than the target screen shrinks to fit inside it", function()
  local saved = { x = -2957, y = -1410, w = 2000, h = 1300 }
  same(place(saved, screens, laptop, SIZE), { x = 0, y = 33, w = 1728, h = 1084 })
end)

test("a frame saved on a screen that is gone is centred on the target", function()
  local saved = { x = 9000, y = 9000, w = 600, h = 500 }
  same(place(saved, screens, laptop, SIZE), { x = 564, y = 33 + 292, w = 600, h = 500 })
end)

print(string.format("%d passed, %d failed", passed, failures))
os.exit(failures == 0 and 0 or 1)

-- Where the panel opens: on the screen you are working on, at the size and spot you last left it.
-- Plain tables in, plain table out, so it can be tested outside Hammerspoon.
local M = {}

local function contains(screen, x, y)
  return x >= screen.x and x <= screen.x + screen.w and y >= screen.y and y <= screen.y + screen.h
end

-- How far along the free space of `from` the panel sat (0 = left/top edge, 1 = right/bottom edge).
local function fraction(pos, start, room)
  if room <= 0 then return 0 end
  return math.max(0, math.min(1, (pos - start) / room))
end

-- saved: the last frame or nil; screens: every screen frame; target: the screen to open on;
-- size: the default {w, h}.
function M.place(saved, screens, target, size)
  local source
  if saved then
    for _, screen in ipairs(screens) do
      if contains(screen, saved.x + saved.w / 2, saved.y + saved.h / 2) then source = screen break end
    end
  end
  local w = math.min((saved or size).w, target.w)
  local h = math.min((saved or size).h, target.h)
  if not source then
    return { x = target.x + (target.w - w) / 2, y = target.y + (target.h - h) / 2, w = w, h = h }
  end
  local fx = fraction(saved.x, source.x, source.w - saved.w)
  local fy = fraction(saved.y, source.y, source.h - saved.h)
  return { x = target.x + fx * (target.w - w), y = target.y + fy * (target.h - h), w = w, h = h }
end

return M

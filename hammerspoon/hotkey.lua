-- The panel's shortcut, written the way people write it: "ctrl+space", "cmd+shift+n", "⌘⇧K".
local M = {}

local NAMES = {
  ctrl = "ctrl", control = "ctrl", cmd = "cmd", command = "cmd",
  alt = "alt", option = "alt", opt = "alt", shift = "shift",
}
local SYMBOLS = { ["⌘"] = "cmd+", ["⇧"] = "shift+", ["⌥"] = "alt+", ["⌃"] = "ctrl+" }
local DEFAULT = { mods = { "ctrl" }, key = "space" }

function M.parse(text)
  if type(text) ~= "string" then return DEFAULT end
  for symbol, name in pairs(SYMBOLS) do text = text:gsub(symbol, name) end
  local parts = {}
  for part in text:lower():gmatch("[^+%s]+") do parts[#parts + 1] = part end
  local key = table.remove(parts)
  if not key or NAMES[key] then return DEFAULT end
  local mods = {}
  for _, part in ipairs(parts) do
    if not NAMES[part] then return DEFAULT end
    mods[#mods + 1] = NAMES[part]
  end
  return { mods = mods, key = key }
end

return M

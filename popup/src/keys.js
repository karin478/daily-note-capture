// Day switching goes by physical key, so ⌘[ / ⌘] work even when the input method types 【 】.
const STEPS = { BracketLeft: -1, BracketRight: 1 };

export function dayStep(e) {
  if (!e.metaKey || e.ctrlKey || e.altKey || e.shiftKey) return null;
  return STEPS[e.code] ?? null;
}

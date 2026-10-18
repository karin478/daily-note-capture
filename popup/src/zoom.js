// ⌘= / ⌘- / ⌘0 zoom, stepping through the same levels as Chrome and Obsidian.
export const ZOOM_LEVELS = [0.5, 0.67, 0.75, 0.8, 0.9, 1, 1.1, 1.25, 1.5, 1.75, 2];

export function stepZoom(current, direction) {
  if (direction === 0) return 1;
  if (direction > 0) return ZOOM_LEVELS.find((z) => z > current + 1e-6) ?? ZOOM_LEVELS.at(-1);
  return ZOOM_LEVELS.findLast((z) => z < current - 1e-6) ?? ZOOM_LEVELS[0];
}

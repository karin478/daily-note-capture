// Times (⌘T) and the dates of daily notes.
export const clock = (d = new Date()) =>
  `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;

// Daily-note dates are local YYYY-MM-DD strings.
export const isoDay = (d = new Date()) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

const parseDay = (day) => {
  const [y, m, d] = day.split('-').map(Number);
  return new Date(y, m - 1, d);
};

export function shiftDay(day, delta) {
  const d = parseDay(day);
  d.setDate(d.getDate() + delta);
  return isoDay(d);
}

export const weekday = (day) => '周' + '日一二三四五六'[parseDay(day).getDay()];

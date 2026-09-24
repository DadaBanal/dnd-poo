// How DICOM's values read on screen. PMC is in Manila; so are the dates.

// "DELA CRUZ^JUAN^^^" -> "DELA CRUZ, Juan"
export function personName(pn: string): string {
  const [family = '', given = ''] = pn.split('^');
  const title = (s: string) => s.toLowerCase().replace(/(^|[\s'-])\p{L}/gu, (m) => m.toUpperCase());
  if (!family && !given) return 'No name';
  return given ? `${family.toUpperCase()}, ${title(given)}` : family.toUpperCase();
}

// A study's date and time (Manila) as epoch milliseconds, or undefined.
export function studyMoment(date: string, time: string): number | undefined {
  const d = /^(\d{4})(\d{2})(\d{2})$/.exec(date);
  if (!d) return undefined;
  const t = /^(\d{2})(\d{2})?(\d{2})?/.exec(time) ?? [];
  const iso = `${d[1]}-${d[2]}-${d[3]}T${t[1] ?? '00'}:${t[2] ?? '00'}:${t[3] ?? '00'}+08:00`;
  const ms = Date.parse(iso);
  return Number.isNaN(ms) ? undefined : ms;
}

const clock = new Intl.DateTimeFormat('en-PH', {
  timeZone: 'Asia/Manila', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false,
});
const dayOnly = new Intl.DateTimeFormat('en-PH', { timeZone: 'Asia/Manila', day: 'numeric', month: 'short', year: 'numeric' });

export function when(ms: number | undefined, hasTime: boolean): string {
  if (ms === undefined) return 'No date';
  return hasTime ? clock.format(ms) : dayOnly.format(ms);
}

// How long ago, compactly: "8 min", "3 h", "2 d".
export function ago(ms: number | undefined, now: number): string {
  if (ms === undefined) return '';
  const minutes = Math.max(0, Math.round((now - ms) / 60_000));
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} h`;
  return `${Math.round(hours / 24)} d`;
}

// "M · 54 y" from sex and birth date (YYYYMMDD).
export function sexAge(sex: string, birth: string, now: number): string {
  const b = /^(\d{4})(\d{2})(\d{2})$/.exec(birth);
  let age = '';
  if (b) {
    const born = new Date(Number(b[1]), Number(b[2]) - 1, Number(b[3]));
    const today = new Date(now);
    let years = today.getFullYear() - born.getFullYear();
    if (today < new Date(today.getFullYear(), born.getMonth(), born.getDate())) years -= 1;
    age = years >= 2 ? `${years} y` : `${Math.max(0, Math.floor((now - born.getTime()) / (30.44 * 86_400_000)))} mo`;
  }
  return [sex, age].filter(Boolean).join(' · ');
}

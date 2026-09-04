import React, { useEffect, useMemo, useRef, useState } from 'react';
import { TrainingCalendar } from '../types';
import { getTrainingCalendar } from '../api/client';
import { SPORTS, isoWeekKey } from '../lib/format';

export { isoWeekKey };

/**
 * Pick a week off a calendar.
 *
 * Stepping back one arrow-press at a time is fine for last week and hopeless
 * for last March. A calendar makes the distance irrelevant, and marking the
 * days that were trained means you can see which week is worth opening before
 * you open it -- an empty fortnight is visible at a glance rather than
 * discovered by paging through it.
 */

const DAY_HEADS = ['M', 'T', 'W', 'T', 'F', 'S', 'S'];

const mondayOf = (d: Date): Date => {
  const out = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  out.setDate(out.getDate() - ((out.getDay() + 6) % 7));
  return out;
};

const iso = (d: Date): string =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

const sportColor = (sport: string): string => {
  const s = (sport || '').toLowerCase();
  if (SPORTS.runs.match(s)) return 'var(--run)';
  if (SPORTS.walks.match(s)) return 'var(--walk)';
  return 'var(--gym)';
};

/** The Mondays of every week the month grid touches, six rows at most. */
const weeksOf = (month: Date): Date[][] => {
  const first = mondayOf(new Date(month.getFullYear(), month.getMonth(), 1));
  const weeks: Date[][] = [];
  const cursor = new Date(first);
  for (let w = 0; w < 6; w++) {
    const row: Date[] = [];
    for (let i = 0; i < 7; i++) {
      row.push(new Date(cursor));
      cursor.setDate(cursor.getDate() + 1);
    }
    weeks.push(row);
    // Stop once the grid has passed the end of the month entirely.
    if (row[6].getMonth() !== month.getMonth() && row[6] > new Date(month.getFullYear(), month.getMonth() + 1, 0)) {
      break;
    }
  }
  return weeks;
};

export const WeekPicker: React.FC<{
  /** The week currently shown, as an ISO week key. */
  selected: string;
  label: string;
  onSelect: (weekKey: string) => void;
}> = ({ selected, label, onSelect }) => {
  const [open, setOpen] = useState(false);
  const [month, setMonth] = useState(() => new Date());
  const [data, setData] = useState<TrainingCalendar | null>(null);
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const key = `${month.getFullYear()}-${String(month.getMonth() + 1).padStart(2, '0')}`;
    let cancelled = false;
    getTrainingCalendar(key)
      .then((d) => { if (!cancelled) setData(d); })
      .catch(() => { if (!cancelled) setData(null); });
    return () => { cancelled = true; };
  }, [open, month]);

  // Clicking away closes it, which is what every calendar does.
  useEffect(() => {
    if (!open) return;
    const away = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    const escape = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', away);
    document.addEventListener('keydown', escape);
    return () => {
      document.removeEventListener('mousedown', away);
      document.removeEventListener('keydown', escape);
    };
  }, [open]);

  const weeks = useMemo(() => weeksOf(month), [month]);
  const today = iso(new Date());
  const earliest = data?.earliest ?? null;

  const monthLabel = month.toLocaleDateString(undefined, { month: 'long', year: 'numeric' });
  // Nothing was recorded before the first activity, so stop offering months.
  const canGoBack = !earliest || mondayOf(new Date(month.getFullYear(), month.getMonth(), 1)) > new Date(earliest);
  const canGoForward = month.getFullYear() < new Date().getFullYear()
    || (month.getFullYear() === new Date().getFullYear() && month.getMonth() < new Date().getMonth());

  const step = (by: number) =>
    setMonth((m) => new Date(m.getFullYear(), m.getMonth() + by, 1));

  return (
    <div className="relative" ref={box}>
      <button onClick={() => setOpen((o) => !o)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-line
                         text-[13px] font-semibold text-fg-strong hover:border-line-strong transition">
        {label}
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
             strokeWidth="2" strokeLinecap="round" className="text-muted">
          <path d="M6 9l6 6 6-6" />
        </svg>
      </button>

      {open && (
        <div className="absolute right-0 z-30 mt-2 w-[19rem] p-3 rounded-xl bg-card border border-line shadow-lg">
          <div className="flex items-center justify-between mb-2">
            <button onClick={() => step(-1)} disabled={!canGoBack} aria-label="Previous month"
                    className="p-1.5 rounded-lg text-muted hover:text-fg hover:bg-surface transition disabled:opacity-25">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   strokeWidth="2" strokeLinecap="round"><path d="M15 18l-6-6 6-6" /></svg>
            </button>
            <span className="text-[13px] font-semibold text-fg-strong">{monthLabel}</span>
            <button onClick={() => step(1)} disabled={!canGoForward} aria-label="Next month"
                    className="p-1.5 rounded-lg text-muted hover:text-fg hover:bg-surface transition disabled:opacity-25">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   strokeWidth="2" strokeLinecap="round"><path d="M9 18l6-6-6-6" /></svg>
            </button>
          </div>

          <div className="grid grid-cols-7 mb-1">
            {DAY_HEADS.map((d, i) => (
              <span key={i} className="text-center text-2xs font-medium text-faint">{d}</span>
            ))}
          </div>

          <div className="space-y-0.5">
            {weeks.map((row) => {
              const key = isoWeekKey(row[0]);
              const isSelected = key === selected;
              // A week with no days yet in the past cannot be recapped.
              const startable = iso(row[0]) <= today;
              return (
                <button key={key} disabled={!startable}
                        onClick={() => { onSelect(key); setOpen(false); }}
                        className={`w-full grid grid-cols-7 rounded-lg transition ${
                          isSelected ? 'bg-accent/12 ring-1 ring-accent'
                                     : startable ? 'hover:bg-surface' : 'opacity-30'}`}>
                  {row.map((day) => {
                    const stamp = iso(day);
                    const entry = data?.days?.[stamp];
                    const outside = day.getMonth() !== month.getMonth();
                    const future = stamp > today;
                    return (
                      <span key={stamp} className="py-1 flex flex-col items-center gap-0.5">
                        <span className={`text-2xs tnum ${
                          stamp === today ? 'font-bold text-accent'
                            : outside || future ? 'text-faint' : 'text-fg'}`}>
                          {day.getDate()}
                        </span>
                        {/* One dot per sport that day, so a week's shape is
                            legible without opening it. */}
                        <span className="flex gap-px h-1 items-center">
                          {(entry?.sports ?? []).slice(0, 3).map((sport) => (
                            <span key={sport} className="h-1 w-1 rounded-full"
                                  style={{ background: sportColor(sport) }} />
                          ))}
                        </span>
                      </span>
                    );
                  })}
                </button>
              );
            })}
          </div>

          <p className="mt-2 pt-2 border-t border-line text-2xs text-faint">
            Pick any day to open that week.
          </p>
        </div>
      )}
    </div>
  );
};

import React, { useEffect, useMemo, useState } from 'react';
import { CycleSummary, CycleCalendarMonth } from '../types';
import {
  getCycleSummary, getCycleCalendar, logCycleDay, unlogCycleDay,
} from '../api/client';
import { Card } from './Stat';
import { Modal, button } from './Modal';
import { describeError } from '../lib/errors';

/**
 * Cycle tracking.
 *
 * Cycle phase moves resting heart rate, perceived effort and how a hard
 * session feels, so it belongs next to the training rather than in a separate
 * app. It is off until switched on, and it stays on this server like
 * everything else here.
 *
 * Predictions are arithmetic on the days that were logged, and they say how
 * confident they are. This is not contraception and not a fertility test, and
 * the interface says so where someone might otherwise assume it.
 */

const PHASE_LABEL: Record<string, string> = {
  period: 'Period',
  follicular: 'Follicular phase',
  ovulation: 'Ovulation expected',
  luteal: 'Luteal phase',
};

const PHASE_NOTE: Record<string, string> = {
  period: 'Iron loss and disturbed sleep can make easy days feel harder than usual.',
  follicular: 'Often when hard sessions feel most repeatable.',
  ovulation: 'Estimated from your cycle length, not measured.',
  luteal: 'Resting heart rate and perceived effort often sit a little higher.',
};

const CONFIDENCE_NOTE: Record<string, string> = {
  low: 'Based on few cycles, so treat it loosely.',
  moderate: 'Your cycles vary a little, so this is approximate.',
  high: 'Your recent cycles have been consistent.',
};

const FLOWS = ['spotting', 'light', 'medium', 'heavy'] as const;

const iso = (d: Date): string =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;

const mondayFirst = (d: Date): number => (d.getDay() + 6) % 7;

const prettyDate = (isoDate: string): string =>
  new Date(isoDate).toLocaleDateString(undefined, { day: 'numeric', month: 'long' });

/** The calendar where days are logged. */
export const CycleCalendarModal: React.FC<{
  isOpen: boolean; onClose: () => void; onChanged: () => void;
}> = ({ isOpen, onClose, onChanged }) => {
  const [month, setMonth] = useState(() => new Date());
  const [data, setData] = useState<CycleCalendarMonth | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const monthKey = `${month.getFullYear()}-${String(month.getMonth() + 1).padStart(2, '0')}`;

  const load = async () => {
    try {
      setData(await getCycleCalendar(monthKey));
      setError(null);
    } catch (e) {
      setError(describeError(e, 'Could not load your calendar'));
    }
  };

  useEffect(() => { if (isOpen) load(); /* eslint-disable-next-line */ }, [isOpen, monthKey]);

  const grid = useMemo(() => {
    const first = new Date(month.getFullYear(), month.getMonth(), 1);
    const daysInMonth = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
    const cells: (Date | null)[] = Array(mondayFirst(first)).fill(null);
    for (let d = 1; d <= daysInMonth; d++) {
      cells.push(new Date(month.getFullYear(), month.getMonth(), d));
    }
    return cells;
  }, [month]);

  if (!isOpen) return null;

  const today = data?.today ?? iso(new Date());

  const tap = async (stamp: string) => {
    if (stamp > today) return;
    setSelected(stamp);
    // Tapping an unlogged day logs it; tapping a logged one only selects it,
    // so a day is never removed by the same gesture that added it.
    if (data && !data.days[stamp]) {
      setBusy(true);
      try {
        await logCycleDay(stamp, null);
        await load();
        onChanged();
      } catch (e) {
        setError(describeError(e, 'Could not save that day'));
      } finally {
        setBusy(false);
      }
    }
  };

  const setFlow = async (flow: string | null) => {
    if (!selected) return;
    setBusy(true);
    try {
      await logCycleDay(selected, flow);
      await load();
      onChanged();
    } catch (e) {
      setError(describeError(e, 'Could not save that day'));
    } finally {
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      await unlogCycleDay(selected);
      await load();
      onChanged();
      setSelected(null);
    } catch (e) {
      setError(describeError(e, 'Could not remove that day'));
    } finally {
      setBusy(false);
    }
  };

  const step = (by: number) =>
    setMonth((m) => new Date(m.getFullYear(), m.getMonth() + by, 1));

  const selectedEntry = selected && data ? data.days[selected] : undefined;

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Cycle calendar"
           subtitle="Tap the days of your period">
      <div className="flex items-center justify-between mb-3">
        <button onClick={() => step(-1)} aria-label="Previous month"
                className="p-1.5 rounded-lg text-muted hover:text-fg hover:bg-surface transition">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2" strokeLinecap="round"><path d="M15 18l-6-6 6-6" /></svg>
        </button>
        <span className="text-[13px] font-semibold text-fg-strong">
          {month.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}
        </span>
        <button onClick={() => step(1)} aria-label="Next month"
                className="p-1.5 rounded-lg text-muted hover:text-fg hover:bg-surface transition">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2" strokeLinecap="round"><path d="M9 18l6-6-6-6" /></svg>
        </button>
      </div>

      <div className="grid grid-cols-7 mb-1">
        {['M', 'T', 'W', 'T', 'F', 'S', 'S'].map((d, i) => (
          <span key={i} className="text-center text-2xs font-medium text-faint">{d}</span>
        ))}
      </div>

      <div className="grid grid-cols-7 gap-1">
        {grid.map((day, i) => {
          if (!day) return <span key={`pad${i}`} />;
          const stamp = iso(day);
          const logged = data?.days[stamp];
          const predicted = data?.predicted.includes(stamp);
          const future = stamp > today;
          const isToday = stamp === today;
          const isSelected = stamp === selected;
          return (
            <button key={stamp} onClick={() => tap(stamp)} disabled={future || busy}
              className={`aspect-square rounded-lg text-[13px] tnum transition relative
                ${logged ? 'bg-accent text-white font-semibold'
                  : predicted ? 'border border-dashed border-accent/60 text-accent'
                  : future ? 'text-faint/50 cursor-default'
                  : 'text-fg hover:bg-surface'}
                ${isSelected ? 'ring-2 ring-offset-1 ring-accent ring-offset-card' : ''}`}>
              {day.getDate()}
              {isToday && (
                <span className={`absolute bottom-1 left-1/2 -translate-x-1/2 h-1 w-1 rounded-full
                  ${logged ? 'bg-white' : 'bg-accent'}`} />
              )}
            </button>
          );
        })}
      </div>

      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-2xs text-faint">
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded bg-accent" /> logged
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded border border-dashed border-accent/60" /> expected
        </span>
      </div>

      {selected && (
        <div className="mt-4 pt-4 border-t border-line">
          <div className="text-xs text-muted mb-2">{prettyDate(selected)}</div>
          {selectedEntry !== undefined ? (
            <>
              <div className="flex gap-1">
                {FLOWS.map((f) => (
                  <button key={f} disabled={busy} onClick={() => setFlow(f)}
                    className={`flex-1 py-1.5 rounded-md text-2xs font-medium capitalize transition ${
                      selectedEntry?.flow === f
                        ? 'bg-accent text-white'
                        : 'bg-surface border border-line text-muted hover:text-fg'}`}>
                    {f}
                  </button>
                ))}
              </div>
              <button disabled={busy} onClick={remove}
                      className="mt-2 text-2xs text-negative hover:underline">
                Remove this day
              </button>
            </>
          ) : (
            <p className="text-2xs text-faint">Not logged.</p>
          )}
        </div>
      )}

      {error && <p className="mt-3 text-xs text-negative">{error}</p>}

      <p className="mt-4 pt-3 border-t border-line text-2xs text-faint">
        Expected days are worked out from the cycles you have logged. This is not
        contraception and not a fertility test.
      </p>

      <div className="flex justify-end pt-3">
        <button onClick={onClose} className={`${button} bg-surface border border-line text-fg`}>
          Done
        </button>
      </div>
    </Modal>
  );
};

/** The home-page summary. Renders nothing unless tracking is switched on. */
export const CycleCard: React.FC<{ refreshKey?: number }> = ({ refreshKey = 0 }) => {
  const [summary, setSummary] = useState<CycleSummary | null>(null);
  const [failed, setFailed] = useState(false);
  const [open, setOpen] = useState(false);
  const [bump, setBump] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getCycleSummary()
      .then((s) => { if (!cancelled) setSummary(s); })
      .catch(() => { if (!cancelled) setFailed(true); });
    return () => { cancelled = true; };
  }, [refreshKey, bump]);

  // A server without the endpoint, or tracking switched off: stay out of the
  // way entirely rather than advertising a feature nobody asked for.
  if (failed || !summary || !summary.enabled) return null;

  const { phase, cycle_day, days_until_next, predicted_next_start, confidence } = summary;

  return (
    <>
      <section className="mt-6">
        <div className="flex items-baseline justify-between mb-3 px-1">
          <h2 className="text-sm font-bold text-fg-strong tracking-tight">Cycle</h2>
          <button onClick={() => setOpen(true)}
                  className="text-2xs text-faint hover:text-muted transition">
            Open calendar
          </button>
        </div>
        <Card className="p-5">
          {summary.periods_recorded === 0 ? (
            <>
              <p className="text-[13px] text-muted">{summary.reason}</p>
              <button onClick={() => setOpen(true)}
                      className="mt-3 text-xs font-semibold text-accent hover:underline">
                Log your first period →
              </button>
            </>
          ) : (
            <>
              <div className="flex items-baseline justify-between gap-3 flex-wrap">
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-bold tnum tracking-tight text-fg-strong">
                    Day {cycle_day}
                  </span>
                  {phase && (
                    <span className="text-sm font-medium text-accent">{PHASE_LABEL[phase]}</span>
                  )}
                </div>
                {summary.average_cycle_days && (
                  <span className="text-xs text-faint tnum">
                    {summary.average_cycle_days}-day average
                  </span>
                )}
              </div>

              {phase && PHASE_NOTE[phase] && (
                <p className="mt-1.5 text-[13px] text-muted">{PHASE_NOTE[phase]}</p>
              )}

              <div className="mt-4 pt-4 border-t border-line">
                {summary.has_prediction && predicted_next_start ? (
                  <>
                    <div className="text-[13px] text-fg">
                      Next period expected{' '}
                      <span className="font-semibold text-fg-strong">
                        {prettyDate(predicted_next_start)}
                      </span>
                      {days_until_next != null && days_until_next >= 0 && (
                        <span className="text-muted">
                          {' '}· in {days_until_next} day{days_until_next === 1 ? '' : 's'}
                        </span>
                      )}
                    </div>
                    <p className="mt-1 text-2xs text-faint">
                      {CONFIDENCE_NOTE[confidence] ?? ''}
                      {summary.cycle_range &&
                        ` Your cycles have run ${summary.cycle_range[0]} to ${summary.cycle_range[1]} days.`}
                    </p>
                  </>
                ) : (
                  <p className="text-[13px] text-muted">{summary.reason}</p>
                )}
              </div>
            </>
          )}
        </Card>
      </section>

      <CycleCalendarModal isOpen={open} onClose={() => setOpen(false)}
                          onChanged={() => setBump((b) => b + 1)} />
    </>
  );
};

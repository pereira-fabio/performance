import React, { useEffect, useState } from 'react';
import { PeriodReport } from '../types';
import { Card } from './Stat';
import { getWeekReport } from '../api/client';
import { pace, duration, isoWeekKey } from '../lib/format';

/**
 * The way into last week's recap, from the home page.
 *
 * It shows enough to be worth a glance on its own -- distance, how that
 * compares, how many days were trained -- so that opening the full recap is a
 * choice rather than the only way to find out whether the week went well.
 *
 * It leads with "last week" because the week it describes has finished. A
 * rolling seven days would change under the reader every day and never invite
 * the verdict a recap is for.
 */
export const LastWeekCard: React.FC<{ onOpen: () => void }> = ({ onOpen }) => {
  const [report, setReport] = useState<PeriodReport | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getWeekReport(0)
      .then((r) => { if (!cancelled) setReport(r); })
      .catch(() => { if (!cancelled) setFailed(true); });
    return () => { cancelled = true; };
  }, []);

  // A server without the recap endpoint yet, or a request that failed: the
  // home page is still perfectly useful without this.
  if (failed) return null;

  const t = report?.totals;
  const km = t?.km ?? 0;
  const delta = report?.deltas?.km;
  // Monday and Tuesday are when a finished week is actually news.
  const fresh = [1, 2].includes(new Date().getDay());

  return (
    <section className="mt-6">
      <div className="flex items-baseline justify-between mb-3 px-1">
        <h2 className="text-sm font-bold text-fg-strong tracking-tight">Last week</h2>
        {fresh && report && !report.empty && (
          <span className="text-2xs font-bold uppercase tracking-wide text-accent">new</span>
        )}
      </div>
      <Card className="overflow-hidden">
        <button onClick={onOpen} disabled={!report}
                className="w-full text-left p-5 hover:bg-surface transition disabled:cursor-default">
          {!report ? (
            <p className="text-[13px] text-muted">Adding up your week…</p>
          ) : report.empty ? (
            <>
              <div className="text-sm font-semibold text-fg-strong">{report.label}</div>
              <p className="mt-1 text-[13px] text-muted">
                Nothing recorded. Open the recap to look further back.
              </p>
            </>
          ) : (
            <>
              <div className="flex items-baseline justify-between gap-3">
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-bold tnum tracking-tight text-fg-strong">
                    {km.toFixed(1)}
                  </span>
                  <span className="text-sm font-medium text-muted">km</span>
                  {delta?.change != null && Math.abs(delta.change) >= 0.05 && (
                    <span className={`text-xs font-semibold tnum ${
                      delta.change > 0 ? 'text-positive' : 'text-caution'}`}>
                      {delta.change > 0 ? '▲' : '▼'} {Math.abs(delta.change).toFixed(1)} km
                    </span>
                  )}
                </div>
                <span className="text-xs font-semibold text-accent shrink-0">
                  Full recap →
                </span>
              </div>
              <div className="mt-1 text-[13px] text-muted">
                {report.label} · {t!.runs} run{t!.runs === 1 ? '' : 's'} ·{' '}
                {t!.days_trained} of {report.day_count} days
                {t!.avg_pace_sec_km ? ` · ${pace(t!.avg_pace_sec_km)}/km average` : ''}
              </div>
            </>
          )}
        </button>
      </Card>
    </section>
  );
};


/**
 * The week you are in.
 *
 * The home page leads with this because it is the only week you can still do
 * anything about. It is deliberately Monday-to-Sunday rather than a rolling
 * seven days: a window that slides forward every morning can never be finished,
 * and "four days trained out of seven" needs a seven to count against.
 */
export const ThisWeekCard: React.FC<{ onOpen: () => void }> = ({ onOpen }) => {
  const [report, setReport] = useState<PeriodReport | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getWeekReport(0, isoWeekKey())
      .then((r) => { if (!cancelled) setReport(r); })
      .catch(() => { if (!cancelled) setFailed(true); });
    return () => { cancelled = true; };
  }, []);

  if (failed) return null;

  const t = report?.totals;
  const days = report?.breakdown.rows ?? [];
  const peak = Math.max(1, ...days.map((d) => d.km ?? 0));
  const today = new Date().toISOString().slice(0, 10);

  return (
    <section className="mt-6">
      <div className="flex items-baseline justify-between mb-3 px-1">
        <h2 className="text-sm font-bold text-fg-strong tracking-tight">This week</h2>
        {report && <span className="text-2xs text-faint">{report.label}</span>}
      </div>
      <Card className="overflow-hidden">
        <button onClick={onOpen} disabled={!report}
                className="w-full text-left p-5 hover:bg-surface transition disabled:cursor-default">
          {!report ? (
            <p className="text-[13px] text-muted">Adding up your week…</p>
          ) : (
            <>
              <div className="flex items-end justify-between gap-4 flex-wrap">
                <div className="flex items-baseline gap-2">
                  <span className="text-4xl font-bold tnum tracking-tight text-fg-strong">
                    {(t!.km ?? 0).toFixed(1)}
                  </span>
                  <span className="text-sm font-medium text-muted">km</span>
                </div>
                <div className="flex items-baseline gap-5 text-right">
                  <span>
                    <span className="block text-sm font-bold tnum text-fg-strong">
                      {duration(t!.moving_sec)}
                    </span>
                    <span className="block text-2xs text-faint">moving</span>
                  </span>
                  <span>
                    <span className="block text-sm font-bold tnum text-fg-strong">
                      {t!.days_trained}/{report.day_count}
                    </span>
                    <span className="block text-2xs text-faint">days</span>
                  </span>
                  <span>
                    <span className="block text-sm font-bold tnum text-fg-strong">
                      {Math.round(t!.load ?? 0)}
                    </span>
                    <span className="block text-2xs text-faint">load</span>
                  </span>
                </div>
              </div>

              {/* Seven slots, always. The empty ones are the point: a rest day
                  missing from the row would read as a week you never had. */}
              <div className="mt-4 flex items-end gap-1.5 h-12">
                {days.map((day) => {
                  const height = day.km ? Math.max(12, ((day.km ?? 0) / peak) * 100) : 4;
                  const isToday = day.date === today;
                  const future = day.date > today;
                  return (
                    <div key={day.date} className="flex-1 flex flex-col items-center gap-1">
                      <div className="w-full rounded-sm transition-all"
                           style={{
                             height: `${height}%`,
                             background: day.km ? 'var(--run)'
                                       : future ? 'var(--line)' : 'var(--line-strong)',
                             opacity: future ? 0.5 : 1,
                           }} />
                      <span className={`text-2xs ${isToday ? 'font-bold text-accent' : 'text-faint'}`}>
                        {day.label[0]}
                      </span>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </button>
      </Card>
    </section>
  );
};

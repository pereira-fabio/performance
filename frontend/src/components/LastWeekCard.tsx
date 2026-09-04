import React, { useEffect, useState } from 'react';
import { PeriodReport } from '../types';
import { Card } from './Stat';
import { getWeekReport } from '../api/client';
import { pace } from '../lib/format';

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

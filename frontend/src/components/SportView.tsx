import React, { useEffect, useRef, useState } from 'react';
import { Activity, DashboardSummary, PMCPoint, BestEffort } from '../types';
import { SportKey, SPORTS, km, duration, weekStart } from '../lib/format';
import { Stat, StatGrid, Section, Empty, Card } from './Stat';
import { ActivityRow } from './ActivityRow';
import { PMCChart } from './PMCChart';
import { PersonalRecordsView } from './PersonalRecordsView';

interface Props {
  tab: SportKey;
  activities: Activity[];
  summary: DashboardSummary | null;
  pmc: PMCPoint[];
  records: BestEffort[];
  onSelect: (a: Activity) => void;
}

const formLabel = (tsb: number) => {
  if (tsb > 15) return { text: 'Fresh', tone: 'positive' as const };
  if (tsb >= -10) return { text: 'Balanced', tone: 'default' as const };
  if (tsb >= -30) return { text: 'Building', tone: 'caution' as const };
  return { text: 'Overloaded', tone: 'negative' as const };
};

// Enough to fill a screen and see where the week went, without laying out
// several hundred rows nobody scrolled to.
const PAGE = 10;

export const SportView: React.FC<Props> = ({ tab, activities, summary, pmc, records, onSelect }) => {
  const [shown, setShown] = useState(PAGE);
  const sentinel = useRef<HTMLDivElement>(null);

  // Switching sports starts the list again rather than inheriting how far the
  // last one was opened.
  useEffect(() => { setShown(PAGE); }, [tab]);

  // Scrolling to the bottom loads the next page on its own; the button below
  // is the same action for anyone who would rather ask for it, and the only
  // one that works without an observer.
  useEffect(() => {
    const node = sentinel.current;
    if (!node || shown >= activities.length) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) setShown((n) => Math.min(n + PAGE, activities.length));
      },
      { rootMargin: '200px' }
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [shown, activities.length]);

  const visible = activities.slice(0, shown);
  const remaining = activities.length - visible.length;
  // Monday to Sunday, not the last seven days. A rolling window answers a
  // different question and slides out from under you every morning; a week you
  // can point at on a calendar is the one people mean by "this week".
  //
  // Every figure here comes from the same set of activities, load included --
  // the server's weekly total is a rolling one, and taking it from there would
  // put four numbers from two different windows in one panel.
  const since = weekStart();
  const thisWeek = activities.filter((a) => new Date(a.start_time) >= since);
  const weekCount = thisWeek.length;
  const weekKm = thisWeek.reduce((s, a) => s + (a.distance_meters || 0), 0);
  const weekTime = thisWeek.reduce((s, a) => s + (a.moving_time_sec || 0), 0);
  const weekLoad = thisWeek.reduce((s, a) => s + (a.r_tss || 0), 0);
  const weekLabel = since.toLocaleDateString(undefined, { day: 'numeric', month: 'short' });

  return (
    <>
      {/* Distance-based sports lead with volume; gym leads with time and effort. */}
      <Card><StatGrid cols={tab === 'runs' ? 4 : 3}>
        {SPORTS[tab].hasPace ? (
          <Stat label="This week" value={weekKm > 0 ? (weekKm / 1000).toFixed(1) : '—'} unit="km"
                sub={`${weekCount} ${weekCount === 1 ? 'session' : 'sessions'}`} />
        ) : (
          <Stat label="This week" value={duration(weekTime)}
                sub={`${weekCount} ${weekCount === 1 ? 'session' : 'sessions'}`} />
        )}
        <Stat label="Time" value={duration(weekTime)} sub="moving" />
        <Stat label="Load" value={weekLoad > 0 ? Math.round(weekLoad) : '—'}
              sub={`since Mon ${weekLabel}`} />
        {tab === 'runs' && summary && (
          <Stat
            label="Form"
            value={summary.tsb > 0 ? `+${Math.round(summary.tsb)}` : Math.round(summary.tsb)}
            sub={formLabel(summary.tsb).text}
            tone={formLabel(summary.tsb).tone}
          />
        )}
      </StatGrid></Card>

      {/* Fitness and fatigue describe running specifically, so they appear
          only here rather than being reused for sports they do not model. */}
      {tab === 'runs' && summary && (
        <Card className="mt-4"><StatGrid cols={3}>
          <Stat label="Fitness" value={Math.round(summary.ctl)} sub="42-day load" tone="accent" />
          <Stat label="Fatigue" value={Math.round(summary.atl)} sub="7-day load" />
          <Stat label="Decoupling" value={summary.avg_decoupling_28d != null ? `${summary.avg_decoupling_28d}%` : '—'}
                sub="28-day average"
                tone={summary.avg_decoupling_28d != null && summary.avg_decoupling_28d > 5 ? 'caution' : 'default'} />
        </StatGrid></Card>
      )}

      {tab === 'runs' && pmc.length > 0 && (
        <Section title="Fitness & fatigue"><PMCChart data={pmc} /></Section>
      )}

      {tab === 'runs' && records.length > 0 && (
        <Section title="Personal records"
                 aside={<span className="text-2xs text-faint">best three at each distance</span>}>
          <PersonalRecordsView
            records={records}
            onSelect={(id) => {
              const found = activities.find((a) => a.id === id);
              if (found) onSelect(found);
            }} />
        </Section>
      )}

      <Section title="History" flush
               aside={<span className="text-xs text-faint tnum">
                 {visible.length} of {activities.length}
               </span>}>
        {activities.length === 0 ? (
          <Empty>No {SPORTS[tab].label.toLowerCase()} recorded yet.</Empty>
        ) : (
          <div>
            {visible.map((a) => <ActivityRow key={a.id} activity={a} onSelect={onSelect} />)}
            {remaining > 0 && (
              <div ref={sentinel} className="p-4 text-center border-t border-line">
                <button
                  onClick={() => setShown((n) => Math.min(n + PAGE, activities.length))}
                  className="text-xs font-semibold text-accent hover:underline">
                  Load {Math.min(PAGE, remaining)} more
                </button>
                <span className="block mt-1 text-2xs text-faint tnum">
                  {remaining} older {remaining === 1 ? 'session' : 'sessions'}
                </span>
              </div>
            )}
          </div>
        )}
      </Section>
    </>
  );
};

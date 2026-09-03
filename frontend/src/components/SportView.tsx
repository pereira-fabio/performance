import React from 'react';
import { Activity, DashboardSummary, PMCPoint, BestEffort } from '../types';
import { SportKey, SPORTS, km, duration } from '../lib/format';
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

export const SportView: React.FC<Props> = ({ tab, activities, summary, pmc, records, onSelect }) => {
  const totals = summary?.by_sport?.[tab === 'runs' ? 'running' : tab === 'walks' ? 'walking' : 'gym'];
  const weekCount = activities.filter(
    (a) => new Date(a.start_time) >= new Date(Date.now() - 7 * 864e5)
  ).length;
  const weekKm = activities
    .filter((a) => new Date(a.start_time) >= new Date(Date.now() - 7 * 864e5))
    .reduce((s, a) => s + (a.distance_meters || 0), 0);
  const weekTime = activities
    .filter((a) => new Date(a.start_time) >= new Date(Date.now() - 7 * 864e5))
    .reduce((s, a) => s + (a.moving_time_sec || 0), 0);

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
        <Stat label="Time" value={duration(weekTime)} sub="moving, 7 days" />
        <Stat label="Load" value={totals ? Math.round(totals.load_7d) : '—'} sub="7-day total" />
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
        <Section title="Personal records"><PersonalRecordsView records={records} /></Section>
      )}

      <Section title="History" flush
               aside={<span className="text-xs text-faint tnum">{activities.length} total</span>}>
        {activities.length === 0 ? (
          <Empty>No {SPORTS[tab].label.toLowerCase()} recorded yet.</Empty>
        ) : (
          <div>
            {activities.map((a) => <ActivityRow key={a.id} activity={a} onSelect={onSelect} />)}
          </div>
        )}
      </Section>
    </>
  );
};

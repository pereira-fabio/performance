import React from 'react';
import { HomeData } from '../types';
import {
  ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, Radar,
  PieChart, Pie, Cell, Tooltip,
} from 'recharts';
import { Card, Stat, StatGrid, Section, Empty } from './Stat';
import { CoachNoteCard } from './CoachNote';
import { LastWeekCard } from './LastWeekCard';
import { CycleCard } from './CycleView';
import { Avatar } from './Avatar';
import { duration, SPORTS, SportKey } from '../lib/format';

const ATTRIBUTE_LABELS: Record<string, string> = {
  endurance: 'Endurance',
  speed: 'Speed',
  volume: 'Volume',
  consistency: 'Consistency',
  recovery: 'Recovery',
};

const sportColor = (sport: string): string => {
  const s = sport.toLowerCase();
  if (['running', 'treadmill'].includes(s)) return 'var(--run)';
  if (['walking', 'hiking'].includes(s)) return 'var(--walk)';
  return 'var(--gym)';
};

export const HomeView: React.FC<{
  data: HomeData | null;
  onTab: (t: SportKey) => void;
  onOpenRecap?: () => void;
  /** Bumped when settings change, so the card re-reads whether it is on. */
  cycleKey?: number;
}> = ({ data, onTab, onOpenRecap, cycleKey }) => {
  if (!data || data.empty) {
    return <Empty>Nothing recorded yet. Sync from your phone to get started.</Empty>;
  }

  const { progression: p, attributes, split, totals, form } = data;
  const radar = Object.entries(attributes).map(([k, v]) => ({
    axis: ATTRIBUTE_LABELS[k] ?? k, value: v,
  }));
  const donut = Object.entries(split).map(([sport, v]) => ({
    name: sport, value: Number(v.hours.toFixed(1)), count: v.count, color: sportColor(sport),
  }));
  const earned = data.achievements.filter((a) => a.earned);
  const next = data.achievements.filter((a) => !a.earned)
                                .sort((a, b) => b.progress - a.progress);

  return (
    <>
      {/* Level sits first: it is the one figure that only ever goes up, which
          makes it a fair summary of everything done so far. */}
      <Card className="p-5">
        <div className="flex items-center gap-4">
          {/* The picture replaces the number, not the level: "Level 7" is
              still written beside it, so nothing is lost by setting one. */}
          <div className="shrink-0 h-14 w-14 rounded-2xl overflow-hidden grid place-items-center
                          bg-accent text-white">
            <Avatar size={56} version={cycleKey}
                    fallback={<span className="text-xl font-bold tnum">{p.level}</span>} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-baseline justify-between">
              <span className="text-sm font-bold text-fg-strong">Level {p.level}</span>
              <span className="text-xs text-muted tnum">
                {p.xp_into_level.toLocaleString()} / {p.xp_for_next.toLocaleString()} XP
              </span>
            </div>
            <div className="mt-2 h-2 rounded-full bg-line overflow-hidden">
              <div className="h-full rounded-full bg-accent transition-all"
                   style={{ width: `${p.progress_pct}%` }} />
            </div>
            <div className="mt-1.5 text-xs text-muted">
              {p.xp.toLocaleString()} XP total
              {data.streak_weeks > 0 && ` · ${data.streak_weeks}-week streak`}
            </div>
          </div>
        </div>
      </Card>

      <Card className="mt-4">
        <StatGrid cols={4}>
          <Stat label="Distance" value={totals.km.toFixed(0)} unit="km" sub="all time" />
          <Stat label="Time" value={totals.hours.toFixed(0)} unit="h" sub={`${totals.activities} sessions`} />
          <Stat label="Fitness" value={Math.round(form.ctl)} tone="accent" sub="running CTL" />
          {/* The subtitle describes resting heart rate, so it is omitted
              rather than saying "not recorded" under the VO2 max figure. */}
          <Stat label="VO₂ max" value={data.vo2_max ? Math.round(data.vo2_max) : '—'}
                sub={data.resting_hr ? `resting ${data.resting_hr} bpm` : undefined} />
        </StatGrid>
      </Card>

      {onOpenRecap && <LastWeekCard onOpen={onOpenRecap} />}

      <CycleCard refreshKey={cycleKey} />

      <CoachNoteCard title="This week so far" />

      <div className="grid md:grid-cols-2 gap-4 mt-6">
        <div>
          <h2 className="text-sm font-bold text-fg-strong mb-3 px-1">Profile</h2>
          <Card className="p-4">
            <div className="h-60">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radar} outerRadius="72%">
                  <PolarGrid stroke="var(--line)" />
                  <PolarAngleAxis dataKey="axis" tick={{ fontSize: 11, fill: 'var(--muted)' }} />
                  <Radar dataKey="value" stroke="var(--accent)" strokeWidth={2}
                         fill="var(--accent)" fillOpacity={0.22} />
                  <Tooltip contentStyle={{
                    background: 'var(--bg)', border: '1px solid var(--line-strong)',
                    borderRadius: 8, fontSize: 12, color: 'var(--fg)',
                  }} formatter={(v: number) => [`${v} / 100`, '']} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>

        <div>
          <h2 className="text-sm font-bold text-fg-strong mb-3 px-1">Where the time goes</h2>
          <Card className="p-4">
            <div className="h-60 flex items-center">
              <ResponsiveContainer width="60%" height="100%">
                <PieChart>
                  <Pie data={donut} dataKey="value" innerRadius="58%" outerRadius="88%"
                       paddingAngle={2} stroke="none">
                    {donut.map((d) => <Cell key={d.name} fill={d.color} />)}
                  </Pie>
                  <Tooltip contentStyle={{
                    background: 'var(--bg)', border: '1px solid var(--line-strong)',
                    borderRadius: 8, fontSize: 12, color: 'var(--fg)',
                  }} formatter={(v: number, n: string) => [`${v} h`, n]} />
                </PieChart>
              </ResponsiveContainer>
              <ul className="flex-1 space-y-2">
                {donut.map((d) => (
                  <li key={d.name} className="flex items-center gap-2 text-xs">
                    <span className="h-2.5 w-2.5 rounded-full shrink-0" style={{ background: d.color }} />
                    <span className="capitalize text-fg flex-1">{d.name}</span>
                    <span className="text-muted tnum">{d.value}h</span>
                  </li>
                ))}
              </ul>
            </div>
          </Card>
        </div>
      </div>

      <Section title="Achievements" flush
               aside={<span className="text-xs text-faint tnum">
                 {earned.length} of {data.achievements.length}
               </span>}>
        <div className="grid sm:grid-cols-2 divide-y sm:divide-y-0 divide-line">
          {[...earned, ...next].map((a, i) => (
            <div key={a.key} className={`flex items-center gap-3 px-5 py-3.5 ${
              i % 2 === 0 ? 'sm:border-r' : ''} border-line sm:border-b`}>
              <span className={`shrink-0 h-8 w-8 rounded-full grid place-items-center text-sm ${
                a.earned ? 'bg-accent text-white' : 'bg-surface text-faint'}`}>
                {a.earned ? '★' : '☆'}
              </span>
              <div className="min-w-0 flex-1">
                <div className={`text-sm font-semibold ${a.earned ? 'text-fg-strong' : 'text-muted'}`}>
                  {a.name}
                </div>
                <div className="text-xs text-muted truncate">{a.detail}</div>
                {!a.earned && (
                  <div className="mt-1.5 h-1 rounded-full bg-line overflow-hidden">
                    <div className="h-full bg-faint rounded-full"
                         style={{ width: `${Math.round(a.progress * 100)}%` }} />
                  </div>
                )}
              </div>
              <span className="text-xs text-faint tnum shrink-0">{a.value}</span>
            </div>
          ))}
        </div>
      </Section>
    </>
  );
};

import React from 'react';
import { HomeData } from '../types';
import { Card, Section, Empty } from './Stat';
import { ThisWeekCard, LastWeekCard } from './WeekCards';
import { CycleCard } from './CycleView';
import { Avatar } from './Avatar';

/**
 * The home page answers "how am I doing right now".
 *
 * Lifetime totals, the attribute profile and the split of time between sports
 * answer a slower question and live under Stats. They are worth looking at
 * occasionally; they were being looked at every time anyone opened the app,
 * above the week they could still change.
 */

export const HomeView: React.FC<{
  data: HomeData | null;
  onOpenRecap?: () => void;
  onOpenThisWeek?: () => void;
  /** Bumped when settings change, so the cycle card re-reads whether it is on. */
  cycleKey?: number;
}> = ({ data, onOpenRecap, onOpenThisWeek, cycleKey }) => {
  if (!data || data.empty) {
    return <Empty>Nothing recorded yet. Sync from your phone to get started.</Empty>;
  }

  const { progression: p } = data;
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

      {onOpenThisWeek && <ThisWeekCard onOpen={onOpenThisWeek} />}

      {onOpenRecap && <LastWeekCard onOpen={onOpenRecap} />}

      <CycleCard refreshKey={cycleKey} />

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

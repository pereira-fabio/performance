import React from 'react';
import { BestEffort } from '../types';
import { pace } from '../lib/format';
import { Empty } from './Stat';

/**
 * The best three efforts at each distance.
 *
 * A personal best on its own does not say whether it was a step or a leap.
 * The two behind it do, and they are what you are actually chasing next --
 * beating your second-fastest 5k is a real result on a day the record is out
 * of reach.
 *
 * Every row opens the run it happened in. A record you cannot get back to is
 * a number without a story.
 */

const clock = (sec: number) => {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  return h > 0
    ? `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
    : `${m}:${s.toString().padStart(2, '0')}`;
};

// Medal colours are a convention, not a theme decision, so they are fixed
// rather than taken from the palette -- and they read on either background.
const MEDALS: Record<number, { ring: string; fill: string; text: string; label: string }> = {
  1: { ring: '#e0a52e', fill: '#e0a52e22', text: '#b8860b', label: 'Fastest' },
  2: { ring: '#a8adb8', fill: '#a8adb822', text: '#8b909a', label: 'Second fastest' },
  3: { ring: '#c07a3e', fill: '#c07a3e22', text: '#a6683a', label: 'Third fastest' },
};

const Medal: React.FC<{ rank: number }> = ({ rank }) => {
  const m = MEDALS[rank] ?? MEDALS[3];
  return (
    <span
      title={m.label}
      className="shrink-0 h-5 w-5 rounded-full grid place-items-center text-2xs font-bold tnum"
      style={{ background: m.fill, border: `1.5px solid ${m.ring}`, color: m.text }}>
      {rank}
    </span>
  );
};

const when = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: '2-digit' })
      : '';

export const PersonalRecordsView: React.FC<{
  records: BestEffort[];
  onSelect?: (activityId: string) => void;
}> = ({ records, onSelect }) => {
  if (!records.length) {
    return <Empty>No records yet — they appear once you have a run with GPS.</Empty>;
  }

  // Grouped in the order the server sent them, which is by distance then rank.
  const byDistance: { label: string; efforts: BestEffort[] }[] = [];
  for (const r of records) {
    const last = byDistance[byDistance.length - 1];
    if (last && last.label === r.label) last.efforts.push(r);
    else byDistance.push({ label: r.label, efforts: [r] });
  }

  return (
    <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-x-6 gap-y-5">
      {byDistance.map(({ label, efforts }) => (
        <div key={label} className="border-t border-line pt-2.5">
          <div className="text-2xs text-faint mb-1.5">{label}</div>
          <div className="space-y-1">
            {efforts.map((r) => {
              const clickable = Boolean(r.activity_id && onSelect);
              const Row = clickable ? 'button' : 'div';
              return (
                <Row
                  key={`${r.rank}-${r.activity_id ?? ''}`}
                  {...(clickable
                    ? { onClick: () => onSelect!(r.activity_id!), type: 'button' as const }
                    : {})}
                  className={`w-full flex items-center gap-2 text-left rounded-md px-1 -mx-1 py-0.5 ${
                    clickable ? 'hover:bg-surface transition cursor-pointer' : ''}`}>
                  <Medal rank={r.rank} />
                  <span className={`tnum tracking-tight text-fg-strong ${
                    r.rank === 1 ? 'text-lg font-semibold' : 'text-[13px] font-medium'}`}>
                    {clock(r.time_seconds)}
                  </span>
                  <span className="text-2xs text-muted tnum">{pace(r.pace_sec_km)}/km</span>
                  <span className="ml-auto text-2xs text-faint tnum shrink-0">
                    {when(r.achieved_at)}
                  </span>
                </Row>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
};

import React from 'react';
import { BestEffort } from '../types';
import { pace } from '../lib/format';
import { Empty } from './Stat';

const clock = (sec: number) => {
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  const s = Math.floor(sec % 60);
  return h > 0
    ? `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`
    : `${m}:${s.toString().padStart(2, '0')}`;
};

export const PersonalRecordsView: React.FC<{ records: BestEffort[] }> = ({ records }) => {
  if (!records.length) return <Empty>No records yet — they appear once you have a run with GPS.</Empty>;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-x-6 gap-y-4">
      {records.map((r) => (
        <div key={r.label} className="border-t border-line pt-2.5">
          <div className="text-2xs text-faint">{r.label}</div>
          <div className="mt-0.5 text-lg font-semibold tnum tracking-tight text-fg-strong">
            {clock(r.time_seconds)}
          </div>
          <div className="text-2xs text-muted tnum">{pace(r.pace_sec_km)} /km</div>
        </div>
      ))}
    </div>
  );
};

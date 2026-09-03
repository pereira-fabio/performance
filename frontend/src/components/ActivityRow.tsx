import React from 'react';
import { Activity } from '../types';
import { pace, duration, km, dateLabel, timeLabel, bucketOf, SPORTS, whyMissing } from '../lib/format';

const ICONS: Record<string, React.ReactNode> = {
  runs: <path d="M13 4a2 2 0 1 0 0-.01M9 20l2-5 3-2-1-4-3 2-2 3M13 13l3 2 1 5" />,
  walks: <path d="M13 4a2 2 0 1 0 0-.01M11 21l1-6 2-2-1-5-3 3-1 4M14 13l2 3v5" />,
  gym: <path d="M6 6v12M18 6v12M3 9v6M21 9v6M6 12h12" />,
};

/**
 * One card per activity. The figures shown depend on what the sport measures:
 * a gym session has no pace, so no pace appears rather than an em dash sitting
 * in a column that could never be filled.
 */
export const ActivityRow: React.FC<{ activity: Activity; onSelect: (a: Activity) => void }> = ({
  activity, onSelect,
}) => {
  const bucket = bucketOf(activity);
  const showPace = SPORTS[bucket].hasPace;
  const drift = activity.aerobic_decoupling_pct;

  return (
    <button onClick={() => onSelect(activity)}
      className="w-full text-left px-5 py-4 border-b border-line last:border-0 hover:bg-surface transition-colors group">
      <div className="flex items-center gap-3.5">
        <span className="shrink-0 h-9 w-9 rounded-full grid place-items-center"
              style={{ background: `color-mix(in srgb, ${SPORTS[bucket].color} 14%, transparent)` }}>
          <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke={SPORTS[bucket].color}
               strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            {ICONS[bucket]}
          </svg>
        </span>

        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold text-fg-strong truncate group-hover:text-accent transition-colors">
            {activity.name}
          </div>
          <div className="text-xs text-muted tnum">
            {dateLabel(activity.start_time)} · {timeLabel(activity.start_time)}
            {drift != null && (
              <span className={drift > 5 ? ' text-caution' : ''}> · {drift}% drift</span>
            )}
          </div>
        </div>

        <div className="flex items-baseline gap-4 sm:gap-6 shrink-0 tnum">
          {showPace && (
            <div className="text-right">
              <div className="text-base font-bold text-fg-strong" title={whyMissing(activity, 'distance')}>
                {km(activity.distance_meters)}
              </div>
              <div className="text-2xs text-faint">km</div>
            </div>
          )}
          {showPace && (
            <div className="text-right hidden sm:block">
              <div className="text-base font-bold text-fg-strong">{pace(activity.avg_pace_sec_km)}</div>
              <div className="text-2xs text-faint">/km</div>
            </div>
          )}
          <div className="text-right">
            <div className="text-base font-bold text-fg-strong">{duration(activity.moving_time_sec)}</div>
            <div className="text-2xs text-faint">time</div>
          </div>
          <div className="text-right hidden sm:block">
            <div className="text-base font-bold text-fg-strong">{activity.avg_hr ?? '—'}</div>
            <div className="text-2xs text-faint">bpm</div>
          </div>
        </div>
      </div>
    </button>
  );
};

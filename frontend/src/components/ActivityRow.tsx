import React from 'react';
import { Activity } from '../types';
import { pace, duration, km, dateLabel, timeLabel, bucketOf, SPORTS, whyMissing } from '../lib/format';

interface Props {
  activity: Activity;
  onSelect: (a: Activity) => void;
}

/**
 * One line per activity. Which figures appear depends on what the sport
 * actually measures: a gym session has no pace, so it shows none rather than
 * an em dash in a column that could never be filled.
 */
export const ActivityRow: React.FC<Props> = ({ activity, onSelect }) => {
  const bucket = bucketOf(activity);
  const showPace = SPORTS[bucket].hasPace;
  const drift = activity.aerobic_decoupling_pct;

  return (
    <button
      onClick={() => onSelect(activity)}
      className="w-full text-left py-3.5 border-b border-line last:border-0 hover:bg-surface transition-colors group"
    >
      <div className="flex items-baseline justify-between gap-4">
        <div className="min-w-0">
          <div className="flex items-baseline gap-2">
            <span className="h-1.5 w-1.5 rounded-full shrink-0" style={{ background: SPORTS[bucket].color }} />
            <span className="text-[13px] text-fg-strong truncate group-hover:text-accent transition-colors">
              {activity.name}
            </span>
          </div>
          <div className="mt-0.5 ml-3.5 text-2xs text-muted tnum">
            {dateLabel(activity.start_time)} · {timeLabel(activity.start_time)}
            {drift != null && (
              <span className={drift > 5 ? 'text-caution' : 'text-muted'}> · {drift}% drift</span>
            )}
          </div>
        </div>

        <div className="flex items-baseline gap-5 shrink-0 tnum text-[13px]">
          {showPace && (
            <span className="text-fg-strong w-16 text-right" title={whyMissing(activity, 'distance')}>
              {km(activity.distance_meters)} <span className="text-2xs text-muted">km</span>
            </span>
          )}
          {showPace && (
            <span className="hidden sm:inline text-muted w-14 text-right"
                  title={whyMissing(activity, 'gap_pace')}>
              {pace(activity.avg_pace_sec_km)}
            </span>
          )}
          <span className="text-muted w-12 text-right">{duration(activity.moving_time_sec)}</span>
          <span className="hidden sm:inline text-muted w-12 text-right">
            {activity.avg_hr ? `${activity.avg_hr}` : '—'}
            <span className="text-2xs"> bpm</span>
          </span>
        </div>
      </div>
    </button>
  );
};

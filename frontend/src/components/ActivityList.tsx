import React from 'react';
import { Activity } from '../types';
import { format, parseISO } from 'date-fns';
import { ChevronRight, Heart, Zap, Flame, Mountain, Footprints, Dumbbell, Bike, Waves, Activity as RunIcon } from 'lucide-react';

const RUNNING_SPORTS = ['running', 'treadmill'];
const isRunning = (sport: string) => RUNNING_SPORTS.includes((sport || 'running').toLowerCase());

// Walks, hikes and gym work are stored and shown, but they are not runs: they
// set no records and do not drive the running fitness curve.
const sportBadge = (sport: string) => {
  switch ((sport || '').toLowerCase()) {
    case 'walking':
      return { label: 'Walk', Icon: Footprints, cls: 'bg-sky-950/60 text-sky-400 border-sky-800/40' };
    case 'hiking':
      return { label: 'Hike', Icon: Mountain, cls: 'bg-lime-950/60 text-lime-400 border-lime-800/40' };
    case 'gym':
    case 'strength':
      return { label: 'Gym', Icon: Dumbbell, cls: 'bg-fuchsia-950/60 text-fuchsia-400 border-fuchsia-800/40' };
    case 'treadmill':
      return { label: 'Treadmill', Icon: RunIcon, cls: 'bg-cyan-950/60 text-cyan-400 border-cyan-800/40' };
    case 'cycling':
      return { label: 'Cycling', Icon: Bike, cls: 'bg-amber-950/60 text-amber-400 border-amber-800/40' };
    case 'swimming':
      return { label: 'Swim', Icon: Waves, cls: 'bg-blue-950/60 text-blue-400 border-blue-800/40' };
    case 'rowing':
      return { label: 'Rowing', Icon: Waves, cls: 'bg-teal-950/60 text-teal-400 border-teal-800/40' };
    case 'other':
      return { label: 'Other', Icon: Dumbbell, cls: 'bg-gray-800 text-gray-400 border-gray-700' };
    default:
      return null;
  }
};

interface ActivityListProps {
  activities: Activity[];
  onSelectActivity: (activity: Activity) => void;
}

export const ActivityList: React.FC<ActivityListProps> = ({
  activities,
  onSelectActivity,
}) => {
  // Helper to format seconds to mm:ss
  const formatPace = (secPerKm?: number) => {
    if (!secPerKm || isNaN(secPerKm) || secPerKm <= 0) return '--:--';
    const mins = Math.floor(secPerKm / 60);
    const secs = Math.round(secPerKm % 60);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  const formatDuration = (totalSec: number) => {
    const hours = Math.floor(totalSec / 3600);
    const mins = Math.floor((totalSec % 3600) / 60);
    const secs = Math.round(totalSec % 60);
    if (hours > 0) {
      return `${hours}h ${mins}m ${secs}s`;
    }
    return `${mins}m ${secs}s`;
  };

  const getDecouplingBadge = (drift?: number) => {
    if (drift === null || drift === undefined) return null;
    if (drift <= 3.0) {
      return (
        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-emerald-950/60 text-emerald-400 border border-emerald-800/40" title="Decoupling < 3%: Excellent Aerobic Base">
          Decoupling {drift}% (Solid)
        </span>
      );
    }
    if (drift <= 5.0) {
      return (
        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-teal-950/60 text-teal-400 border border-teal-800/40" title="Decoupling 3-5%: Good Aerobic Fitness">
          Decoupling {drift}% (Good)
        </span>
      );
    }
    return (
      <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-rose-950/60 text-rose-400 border border-rose-800/40" title="Decoupling > 5%: Significant Cardiac Drift / Fatigue">
        Decoupling {drift}% (Drift)
      </span>
    );
  };

  if (activities.length === 0) {
    return (
      <div className="bg-gray-900/80 border border-gray-800 rounded-2xl p-12 text-center">
        <RunIcon className="w-12 h-12 text-gray-600 mx-auto mb-3 animate-pulse" />
        <h3 className="text-base font-bold text-gray-200">No Running Activities Yet</h3>
        <p className="text-xs text-gray-400 max-w-md mx-auto mt-1">
          Connect your Android phone with Health Connect to automatically sync your runs, or use the "Import GPX" button above.
        </p>
      </div>
    );
  }

  return (
    <div className="bg-gray-900/90 backdrop-blur border border-gray-800/80 rounded-2xl overflow-hidden shadow-lg">
      <div className="p-4 sm:p-5 border-b border-gray-800 flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-white tracking-tight">Recent Workouts</h2>
          <p className="text-xs text-gray-400 mt-0.5">Scientific breakdown & physiological performance</p>
        </div>
        <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-gray-800 text-gray-300">
          {(() => {
            const runs = activities.filter((a) => isRunning(a.sport_type)).length;
            const other = activities.length - runs;
            return other > 0 ? `${runs} runs · ${other} other` : `${runs} runs`;
          })()}
        </span>
      </div>

      <div className="divide-y divide-gray-800/60">
        {activities.map((activity) => {
          const distKm = (activity.distance_meters / 1000).toFixed(2);
          const paceStr = formatPace(activity.avg_pace_sec_km);
          const gapStr = formatPace(activity.gap_pace_sec_km);
          const durationStr = formatDuration(activity.moving_time_sec);

          return (
            <div
              key={activity.id}
              onClick={() => onSelectActivity(activity)}
              className="p-4 sm:p-5 hover:bg-gray-800/40 cursor-pointer transition flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 group"
            >
              <div className="flex items-start space-x-3.5">
                <div
                  className={`w-10 h-10 rounded-xl bg-gray-800 border border-gray-700 flex items-center justify-center group-hover:border-cyan-500/50 group-hover:scale-105 transition ${
                    isRunning(activity.sport_type) ? 'text-cyan-400' : 'text-gray-400'
                  }`}
                >
                  {(() => {
                    const badge = sportBadge(activity.sport_type);
                    const Icon = badge && !isRunning(activity.sport_type) ? badge.Icon : RunIcon;
                    return <Icon className="w-5 h-5" />;
                  })()}
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                    <h3 className="text-sm font-bold text-white group-hover:text-cyan-400 transition">
                      {activity.name}
                    </h3>
                    {(() => {
                      const badge = sportBadge(activity.sport_type);
                      if (!badge || isRunning(activity.sport_type)) return null;
                      return (
                        <span
                          className={`px-2 py-0.5 rounded-full text-[10px] font-bold border ${badge.cls}`}
                          title="Not a run: excluded from personal records and the fitness chart"
                        >
                          {badge.label}
                        </span>
                      );
                    })()}
                    {isRunning(activity.sport_type) && getDecouplingBadge(activity.aerobic_decoupling_pct)}
                  </div>
                  <div className="flex items-center space-x-2 text-xs text-gray-400 mt-1">
                    <span>
                      {format(parseISO(activity.start_time), 'EEEE, MMM d, yyyy · h:mm a')}
                    </span>
                    <span>•</span>
                    <span className="capitalize">{activity.source.replace('_', ' ')}</span>
                  </div>
                </div>
              </div>

              {/* Key Metrics Grid */}
              <div className="flex items-center flex-wrap gap-4 sm:gap-6 text-xs w-full sm:w-auto justify-between sm:justify-end border-t sm:border-t-0 pt-3 sm:pt-0 border-gray-800/80">
                {/* Distance */}
                <div>
                  <span className="text-[10px] uppercase font-semibold text-gray-500 block">Distance</span>
                  <span className="font-extrabold text-sm text-gray-100">{distKm} km</span>
                </div>

                {/* Pace & GAP */}
                <div>
                  <span className="text-[10px] uppercase font-semibold text-gray-500 block">Pace / GAP</span>
                  <div className="flex items-center space-x-1">
                    <span className="font-bold text-sm text-cyan-400 font-mono">{paceStr}</span>
                    <span className="text-[10px] text-gray-400 font-mono">({gapStr})</span>
                  </div>
                </div>

                {/* Duration */}
                <div>
                  <span className="text-[10px] uppercase font-semibold text-gray-500 block">Duration</span>
                  <span className="font-semibold text-xs text-gray-200">{durationStr}</span>
                </div>

                {/* Heart Rate */}
                {activity.avg_hr && (
                  <div>
                    <span className="text-[10px] uppercase font-semibold text-gray-500 block">Avg HR</span>
                    <div className="flex items-center space-x-1 text-rose-400">
                      <Heart className="w-3 h-3" />
                      <span className="font-bold text-xs">{activity.avg_hr} bpm</span>
                    </div>
                  </div>
                )}

                {/* rTSS */}
                {activity.r_tss && (
                  <div>
                    <span className="text-[10px] uppercase font-semibold text-gray-500 block">rTSS</span>
                    <span className="font-bold text-xs text-amber-400">{activity.r_tss}</span>
                  </div>
                )}

                <ChevronRight className="w-4 h-4 text-gray-600 group-hover:text-cyan-400 group-hover:translate-x-0.5 transition hidden sm:block" />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

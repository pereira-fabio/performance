import React from 'react';
import { BestEffort } from '../types';
import { Award, Zap, Trophy, Timer } from 'lucide-react';

interface PersonalRecordsViewProps {
  records: BestEffort[];
}

export const PersonalRecordsView: React.FC<PersonalRecordsViewProps> = ({ records }) => {
  const formatPace = (secPerKm: number) => {
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

  return (
    <div className="space-y-6">
      <div className="bg-gray-900/90 backdrop-blur border border-gray-800 rounded-2xl p-6 shadow-lg">
        <div className="flex items-center space-x-3 mb-2">
          <div className="p-2.5 rounded-xl bg-amber-500/10 text-amber-400 border border-amber-500/20">
            <Trophy className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white tracking-tight">All-Time Personal Records</h1>
            <p className="text-xs text-gray-400">Calculated automatically from your fastest segments</p>
          </div>
        </div>
      </div>

      {records.length === 0 ? (
        <div className="bg-gray-900/80 border border-gray-800 rounded-2xl p-12 text-center text-gray-500 text-sm">
          No records calculated yet. Sync running workouts to automatically extract personal bests!
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {records.map((rec, idx) => (
            <div
              key={idx}
              className="bg-gray-900/80 border border-gray-800 rounded-2xl p-5 hover:border-cyan-500/40 transition shadow-sm group"
            >
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-extrabold text-white tracking-wide">{rec.label}</span>
                <span className="p-1.5 rounded-lg bg-amber-500/10 text-amber-400">
                  <Award className="w-4 h-4" />
                </span>
              </div>

              <div className="text-3xl font-black text-cyan-400 font-mono tracking-tight">
                {formatDuration(rec.time_seconds)}
              </div>

              <div className="mt-3 flex items-center justify-between text-xs text-gray-400 pt-3 border-t border-gray-800">
                <span>Avg Pace</span>
                <span className="font-bold text-gray-200 font-mono">{formatPace(rec.pace_sec_km)} /km</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

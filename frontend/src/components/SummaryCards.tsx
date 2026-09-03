import React from 'react';
import { DashboardSummary } from '../types';
import { Flame, Activity, Zap, BatteryCharging, Heart, ShieldAlert } from 'lucide-react';

interface SummaryCardsProps {
  summary: DashboardSummary | null;
}

export const SummaryCards: React.FC<SummaryCardsProps> = ({ summary }) => {
  if (!summary) return null;

  // Format form status
  const getFormStatus = (tsb: number) => {
    if (tsb > 15) return { label: 'Transition / Very Fresh', color: 'text-emerald-400', bg: 'bg-emerald-950/40 border-emerald-800/40' };
    if (tsb >= 5) return { label: 'Fresh / Race Ready', color: 'text-teal-300', bg: 'bg-teal-950/40 border-teal-800/40' };
    if (tsb >= -10) return { label: 'Optimal Training Zone', color: 'text-cyan-400', bg: 'bg-cyan-950/40 border-cyan-800/40' };
    if (tsb >= -30) return { label: 'Productive Fatigue', color: 'text-amber-400', bg: 'bg-amber-950/40 border-amber-800/40' };
    return { label: 'High Fatigue / Overload', color: 'text-rose-400', bg: 'bg-rose-950/40 border-rose-800/40' };
  };

  const formStatus = getFormStatus(summary.tsb);

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      {/* 7-Day Training Volume */}
      <div className="bg-gray-900/80 backdrop-blur border border-gray-800/80 rounded-2xl p-4 shadow-sm hover:border-gray-700 transition">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">7-Day Run Volume</span>
          <div className="p-2 rounded-xl bg-cyan-950/50 text-cyan-400 border border-cyan-800/30">
            <Activity className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3 flex items-baseline space-x-2">
          <span className="text-3xl font-extrabold text-white tracking-tight">{summary.volume_7d_km}</span>
          <span className="text-sm font-semibold text-gray-400">km</span>
        </div>
        <div className="mt-2 flex items-center justify-between text-xs text-gray-400">
          <span>{summary.runs_7d_count} runs</span>
          <span className="text-cyan-400 font-semibold">{summary.tss_7d} TSS</span>
        </div>
        {summary.other_sports_7d && Object.keys(summary.other_sports_7d).length > 0 && (
          <div className="mt-1.5 pt-1.5 border-t border-gray-800/80 text-[11px] text-gray-500">
            {/* Cross-training is shown, but kept out of run volume and the fitness curve. */}
            Also:{' '}
            {Object.entries(summary.other_sports_7d)
              .map(([sport, v]) => `${v.count} ${sport}${v.km > 0 ? ` (${v.km} km)` : ''}`)
              .join(', ')}
          </div>
        )}
      </div>

      {/* Fitness (CTL) & Fatigue (ATL) */}
      <div className="bg-gray-900/80 backdrop-blur border border-gray-800/80 rounded-2xl p-4 shadow-sm hover:border-gray-700 transition">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Fitness vs Fatigue</span>
          <div className="p-2 rounded-xl bg-blue-950/50 text-blue-400 border border-blue-800/30">
            <Zap className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3 flex items-center space-x-4">
          <div>
            <span className="text-xs text-gray-400 block font-medium">CTL (Fitness)</span>
            <span className="text-2xl font-black text-cyan-400">{summary.ctl}</span>
          </div>
          <div className="h-8 w-px bg-gray-800"></div>
          <div>
            <span className="text-xs text-gray-400 block font-medium">ATL (Fatigue)</span>
            <span className="text-2xl font-black text-rose-400">{summary.atl}</span>
          </div>
        </div>
        <div className="mt-2 text-xs text-gray-400">
          ACWR Workload Ratio: <span className="font-semibold text-gray-200">{summary.acwr}</span>
        </div>
      </div>

      {/* Form (TSB) */}
      <div className="bg-gray-900/80 backdrop-blur border border-gray-800/80 rounded-2xl p-4 shadow-sm hover:border-gray-700 transition">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Form (TSB)</span>
          <div className="p-2 rounded-xl bg-violet-950/50 text-violet-400 border border-violet-800/30">
            <BatteryCharging className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3 flex items-baseline space-x-2">
          <span className={`text-3xl font-extrabold tracking-tight ${summary.tsb >= 0 ? 'text-emerald-400' : 'text-amber-400'}`}>
            {summary.tsb > 0 ? `+${summary.tsb}` : summary.tsb}
          </span>
        </div>
        <div className="mt-2">
          <span className={`inline-block px-2 py-0.5 rounded text-[11px] font-semibold border ${formStatus.bg} ${formStatus.color}`}>
            {formStatus.label}
          </span>
        </div>
      </div>

      {/* Aerobic Decoupling Baseline */}
      <div className="bg-gray-900/80 backdrop-blur border border-gray-800/80 rounded-2xl p-4 shadow-sm hover:border-gray-700 transition">
        <div className="flex items-center justify-between">
          <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">Aerobic Decoupling</span>
          <div className="p-2 rounded-xl bg-teal-950/50 text-teal-400 border border-teal-800/30">
            <Heart className="w-4 h-4" />
          </div>
        </div>
        <div className="mt-3 flex items-baseline space-x-2">
          <span className="text-3xl font-extrabold text-white tracking-tight">
            {summary.avg_decoupling_28d !== null && summary.avg_decoupling_28d !== undefined ? `${summary.avg_decoupling_28d}%` : '--'}
          </span>
        </div>
        <div className="mt-2 text-xs text-gray-400">
          {summary.avg_decoupling_28d !== null && summary.avg_decoupling_28d !== undefined ? (
            summary.avg_decoupling_28d <= 5 ? (
              <span className="text-emerald-400 font-semibold">Solid Aerobic Base (&lt;5% drift)</span>
            ) : (
              <span className="text-amber-400 font-semibold">Cardiovascular Drift detected</span>
            )
          ) : (
            <span>28-day moving average</span>
          )}
        </div>
      </div>
    </div>
  );
};

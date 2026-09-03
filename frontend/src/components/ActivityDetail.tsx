import React, { useEffect, useState } from 'react';
import { Activity, StreamPoint } from '../types';
import { format, parseISO } from 'date-fns';
import {
  ArrowLeft,
  Heart,
  Zap,
  Flame,
  Mountain,
  Gauge,
  Activity as RunIcon,
  Award,
  Timer,
  Info,
  Trash2,
} from 'lucide-react';
import { MapContainer, TileLayer, Polyline, Marker, Popup } from 'react-leaflet';
import L from 'leaflet';
import {
  ResponsiveContainer,
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  BarChart,
  Bar,
} from 'recharts';

// Fix Leaflet marker icons
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

interface ActivityDetailProps {
  activity: Activity;
  onBack: () => void;
  onDelete: (id: string) => void;
}

export const ActivityDetail: React.FC<ActivityDetailProps> = ({
  activity,
  onBack,
  onDelete,
}) => {
  const [activeChartMetric, setActiveChartMetric] = useState<'all' | 'hr' | 'pace' | 'elevation'>('all');

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

  // Extract GPS coordinates for Leaflet
  const points: StreamPoint[] = activity.stream_data?.points || [];
  const validGpsPoints = points.filter((p) => p.lat !== undefined && p.lng !== undefined && p.lat !== null && p.lng !== null);
  const polylineCoords: [number, number][] = validGpsPoints.map((p) => [p.lat!, p.lng!]);

  // Downsample chart data to 200 points for silky smooth rendering
  const chartData = React.useMemo(() => {
    if (points.length === 0) return [];
    const step = Math.max(1, Math.floor(points.length / 200));
    return points.filter((_, idx) => idx % step === 0).map((p) => {
      const paceSec = p.speed > 0.5 ? 1000 / p.speed : 0;
      const gapSec = p.gap_speed > 0.5 ? 1000 / p.gap_speed : 0;
      return {
        distKm: Number((p.distance / 1000).toFixed(2)),
        timeSec: Math.round(p.timestamp_offset),
        hr: p.heart_rate || null,
        elevation: p.altitude ? Math.round(p.altitude) : null,
        paceSec: paceSec > 0 && paceSec < 900 ? paceSec : null,
        gapSec: gapSec > 0 && gapSec < 900 ? gapSec : null,
        cadence: p.cadence || null,
      };
    });
  }, [points]);

  // HR Zones data for bar chart
  const hrZonesData = React.useMemo(() => {
    if (!activity.hr_zone_seconds) return [];
    const names: Record<string, string> = {
      z1: 'Z1 Recovery',
      z2: 'Z2 Aerobic',
      z3: 'Z3 Tempo',
      z4: 'Z4 Threshold',
      z5: 'Z5 VO2 Max',
    };
    const colors: Record<string, string> = {
      z1: '#64748b',
      z2: '#06b6d4',
      z3: '#10b981',
      z4: '#f59e0b',
      z5: '#ef4444',
    };
    return Object.entries(activity.hr_zone_seconds).map(([key, sec]) => ({
      zone: names[key] || key.toUpperCase(),
      minutes: Math.round(sec / 60),
      color: colors[key] || '#38bdf8',
    }));
  }, [activity.hr_zone_seconds]);

  return (
    <div className="space-y-6 pb-12">
      {/* Top Bar with Back Button & Actions */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className="flex items-center space-x-2 text-sm font-semibold text-gray-400 hover:text-white bg-gray-900 border border-gray-800 px-3.5 py-1.5 rounded-xl transition"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back to Dashboard</span>
        </button>

        <button
          onClick={() => {
            if (confirm('Are you sure you want to delete this activity?')) {
              onDelete(activity.id);
            }
          }}
          className="flex items-center space-x-1.5 text-xs text-rose-400 hover:text-rose-300 bg-rose-950/40 border border-rose-900/40 px-3 py-1.5 rounded-xl transition"
        >
          <Trash2 className="w-3.5 h-3.5" />
          <span>Delete Run</span>
        </button>
      </div>

      {/* Main Header & Title */}
      <div className="bg-gray-900/90 backdrop-blur border border-gray-800 rounded-2xl p-5 sm:p-6 shadow-lg">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center space-x-3">
              <h1 className="text-2xl font-black text-white tracking-tight">{activity.name}</h1>
              <span className="text-xs uppercase font-bold tracking-wider px-2 py-0.5 rounded bg-cyan-950 text-cyan-400 border border-cyan-800">
                {activity.sport_type}
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-1">
              {format(parseISO(activity.start_time), 'EEEE, MMMM d, yyyy · h:mm a')} · Source: {activity.source}
            </p>
          </div>

          {/* Primary High-level Metrics Pill Bar */}
          <div className="flex items-center flex-wrap gap-4 text-sm bg-gray-950/60 p-3 rounded-xl border border-gray-800">
            <div>
              <span className="text-[10px] uppercase font-bold text-gray-500 block">Distance</span>
              <span className="text-xl font-black text-white">{(activity.distance_meters / 1000).toFixed(2)} <span className="text-xs text-gray-400 font-normal">km</span></span>
            </div>
            <div className="h-6 w-px bg-gray-800"></div>
            <div>
              <span className="text-[10px] uppercase font-bold text-gray-500 block">Moving Time</span>
              <span className="text-lg font-black text-white">{formatDuration(activity.moving_time_sec)}</span>
            </div>
            <div className="h-6 w-px bg-gray-800"></div>
            <div>
              <span className="text-[10px] uppercase font-bold text-gray-500 block">Avg Pace</span>
              <span className="text-lg font-black text-cyan-400 font-mono">{formatPace(activity.avg_pace_sec_km)}</span>
            </div>
            <div className="h-6 w-px bg-gray-800"></div>
            <div>
              <span className="text-[10px] uppercase font-bold text-gray-500 block">GAP Pace</span>
              <span className="text-lg font-black text-teal-300 font-mono">{formatPace(activity.gap_pace_sec_km)}</span>
            </div>
          </div>
        </div>

        {/* Physiology Deep Dive Cards Grid */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mt-6 pt-6 border-t border-gray-800/80">
          {/* Decoupling */}
          <div className="bg-gray-950/50 p-3 rounded-xl border border-gray-800">
            <span className="text-[10px] uppercase font-bold text-gray-400 block">Aerobic Decoupling</span>
            <span className={`text-base font-extrabold ${
              activity.aerobic_decoupling_pct !== undefined && activity.aerobic_decoupling_pct !== null
                ? activity.aerobic_decoupling_pct <= 5
                  ? 'text-emerald-400'
                  : 'text-rose-400'
                : 'text-gray-400'
            }`}>
              {activity.aerobic_decoupling_pct !== undefined && activity.aerobic_decoupling_pct !== null ? `${activity.aerobic_decoupling_pct}%` : '--'}
            </span>
            <span className="text-[10px] text-gray-500 block mt-0.5">Pa:HR cardiac drift</span>
          </div>

          {/* rTSS */}
          <div className="bg-gray-950/50 p-3 rounded-xl border border-gray-800">
            <span className="text-[10px] uppercase font-bold text-gray-400 block">Training Stress (rTSS)</span>
            <span className="text-base font-extrabold text-amber-400">{activity.r_tss || '--'}</span>
            <span className="text-[10px] text-gray-500 block mt-0.5">Intensity: {activity.intensity_factor || '--'} IF</span>
          </div>

          {/* Heart Rate */}
          <div className="bg-gray-950/50 p-3 rounded-xl border border-gray-800">
            <span className="text-[10px] uppercase font-bold text-gray-400 block">Heart Rate</span>
            <span className="text-base font-extrabold text-rose-400">{activity.avg_hr ? `${activity.avg_hr} bpm` : '--'}</span>
            <span className="text-[10px] text-gray-500 block mt-0.5">Max: {activity.max_hr || '--'} bpm</span>
          </div>

          {/* Cadence & Stride */}
          <div className="bg-gray-950/50 p-3 rounded-xl border border-gray-800">
            <span className="text-[10px] uppercase font-bold text-gray-400 block">Cadence & Stride</span>
            <span className="text-base font-extrabold text-violet-400">{activity.avg_cadence ? `${Math.round(activity.avg_cadence)} spm` : '--'}</span>
            <span className="text-[10px] text-gray-500 block mt-0.5">Stride: {activity.avg_stride_length_m || '--'} m</span>
          </div>

          {/* Elevation */}
          <div className="bg-gray-950/50 p-3 rounded-xl border border-gray-800">
            <span className="text-[10px] uppercase font-bold text-gray-400 block">Elevation Gain</span>
            <span className="text-base font-extrabold text-emerald-400">
              {activity.elevation_gain_m !== null && activity.elevation_gain_m !== undefined
                ? `+${Math.round(activity.elevation_gain_m)} m`
                : '--'}
            </span>
            <span className="text-[10px] text-gray-500 block mt-0.5">
              {activity.elevation_loss_m !== null && activity.elevation_loss_m !== undefined
                ? `Loss: -${Math.round(activity.elevation_loss_m)} m`
                : 'Not recorded by device'}
            </span>
          </div>

          {/* TRIMP */}
          <div className="bg-gray-950/50 p-3 rounded-xl border border-gray-800">
            <span className="text-[10px] uppercase font-bold text-gray-400 block">Banister TRIMP</span>
            <span className="text-base font-extrabold text-cyan-400">{activity.trimp_banister || '--'}</span>
            <span className="text-[10px] text-gray-500 block mt-0.5">Edwards: {activity.trimp_edwards || '--'}</span>
          </div>
        </div>
      </div>

      {/* Interactive Map & Route Viewer */}
      {polylineCoords.length > 0 && (
        <div className="bg-gray-900/90 backdrop-blur border border-gray-800 rounded-2xl p-4 sm:p-5 shadow-lg">
          <h2 className="text-base font-bold text-white mb-3 flex items-center space-x-2">
            <span>GPS Route Map</span>
          </h2>
          <div className="h-80 sm:h-96 w-full rounded-xl overflow-hidden border border-gray-800">
            <MapContainer
              bounds={polylineCoords}
              scrollWheelZoom={false}
              className="h-full w-full"
            >
              <TileLayer
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
                url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
              />
              <Polyline
                positions={polylineCoords}
                pathOptions={{ color: '#06b6d4', weight: 4, opacity: 0.9 }}
              />
              <Marker position={polylineCoords[0]}>
                <Popup>Start Point</Popup>
              </Marker>
              <Marker position={polylineCoords[polylineCoords.length - 1]}>
                <Popup>Finish Point</Popup>
              </Marker>
            </MapContainer>
          </div>
        </div>
      )}

      {/* Multi-Stream Interactive Elevation, HR, Pace Chart */}
      {chartData.length > 0 && (
        <div className="bg-gray-900/90 backdrop-blur border border-gray-800 rounded-2xl p-5 shadow-lg">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between pb-4 border-b border-gray-800 gap-3">
            <div>
              <h2 className="text-base font-bold text-white">Interactive Workout Streams</h2>
              <p className="text-xs text-gray-400 mt-0.5">Elevation, Heart Rate, Pace, and Cadence over distance</p>
            </div>

            {/* Filter Buttons */}
            <div className="flex items-center space-x-1 bg-gray-950 p-1 rounded-xl border border-gray-800 text-xs">
              <button
                onClick={() => setActiveChartMetric('all')}
                className={`px-3 py-1 rounded-lg font-semibold transition ${activeChartMetric === 'all' ? 'bg-cyan-500 text-white' : 'text-gray-400'}`}
              >
                All Metrics
              </button>
              <button
                onClick={() => setActiveChartMetric('hr')}
                className={`px-3 py-1 rounded-lg font-semibold transition ${activeChartMetric === 'hr' ? 'bg-rose-500 text-white' : 'text-gray-400'}`}
              >
                Heart Rate
              </button>
              <button
                onClick={() => setActiveChartMetric('pace')}
                className={`px-3 py-1 rounded-lg font-semibold transition ${activeChartMetric === 'pace' ? 'bg-teal-500 text-white' : 'text-gray-400'}`}
              >
                Pace / GAP
              </button>
              <button
                onClick={() => setActiveChartMetric('elevation')}
                className={`px-3 py-1 rounded-lg font-semibold transition ${activeChartMetric === 'elevation' ? 'bg-emerald-500 text-white' : 'text-gray-400'}`}
              >
                Elevation
              </button>
            </div>
          </div>

          <div className="h-72 sm:h-80 w-full mt-4">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={chartData} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis
                  dataKey="distKm"
                  stroke="#64748b"
                  tick={{ fontSize: 11, fill: '#94a3b8' }}
                  tickFormatter={(val) => `${val}k`}
                />
                <YAxis yAxisId="hr" orientation="left" stroke="#f43f5e" domain={['auto', 'auto']} tick={{ fontSize: 10 }} />
                <YAxis yAxisId="alt" orientation="right" stroke="#10b981" domain={['auto', 'auto']} tick={{ fontSize: 10 }} />

                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0f172a',
                    borderColor: '#334155',
                    borderRadius: '0.75rem',
                    fontSize: '12px',
                  }}
                  formatter={(val: any, name: string) => {
                    if (name === 'Pace' || name === 'GAP Pace') {
                      return [formatPace(Number(val)), name];
                    }
                    return [val, name];
                  }}
                />
                <Legend verticalAlign="top" height={36} wrapperStyle={{ fontSize: '11px' }} />

                {(activeChartMetric === 'all' || activeChartMetric === 'elevation') && (
                  <Area
                    yAxisId="alt"
                    type="monotone"
                    dataKey="elevation"
                    name="Elevation (m)"
                    fill="#10b981"
                    stroke="#10b981"
                    fillOpacity={0.15}
                  />
                )}

                {(activeChartMetric === 'all' || activeChartMetric === 'hr') && (
                  <Line
                    yAxisId="hr"
                    type="monotone"
                    dataKey="hr"
                    name="Heart Rate (bpm)"
                    stroke="#f43f5e"
                    strokeWidth={2}
                    dot={false}
                  />
                )}

                {(activeChartMetric === 'all' || activeChartMetric === 'pace') && (
                  <Line
                    yAxisId="hr"
                    type="monotone"
                    dataKey="cadence"
                    name="Cadence (spm)"
                    stroke="#8b5cf6"
                    strokeWidth={1.5}
                    dot={false}
                  />
                )}
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Aerobic Decoupling & Physiology Analysis */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Decoupling Explanation */}
        <div className="bg-gray-900/90 backdrop-blur border border-gray-800 rounded-2xl p-5 shadow-lg flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between pb-3 border-b border-gray-800">
              <h2 className="text-base font-bold text-white flex items-center space-x-2">
                <Heart className="w-4 h-4 text-teal-400" />
                <span>Aerobic Decoupling (Pa:HR Drift)</span>
              </h2>
              <span className={`text-xs font-bold px-2.5 py-1 rounded-lg border ${
                activity.aerobic_decoupling_pct !== undefined && activity.aerobic_decoupling_pct !== null
                  ? activity.aerobic_decoupling_pct <= 5
                    ? 'bg-emerald-950/60 text-emerald-400 border-emerald-800/40'
                    : 'bg-rose-950/60 text-rose-400 border-rose-800/40'
                  : 'bg-gray-800 text-gray-400 border-gray-700'
              }`}>
                {activity.aerobic_decoupling_pct !== undefined && activity.aerobic_decoupling_pct !== null ? `${activity.aerobic_decoupling_pct}% Drift` : 'N/A'}
              </span>
            </div>

            <p className="text-xs text-gray-300 leading-relaxed mt-3">
              Aerobic Decoupling calculates the cardiovascular drift by comparing your <strong>Aerobic Efficiency (EF = Speed / Heart Rate)</strong> during the first half of the run against the second half.
            </p>

            <div className="mt-4 space-y-2 text-xs">
              <div className="p-2.5 rounded-xl bg-gray-950 border border-gray-800 flex items-center justify-between">
                <span className="text-gray-400">Overall Aerobic Efficiency (EF):</span>
                <span className="font-bold text-cyan-400">{activity.aerobic_efficiency_factor ? `${activity.aerobic_efficiency_factor} m/min/bpm` : '--'}</span>
              </div>
              <div className="p-2.5 rounded-xl bg-gray-950 border border-gray-800 flex items-center justify-between">
                <span className="text-gray-400">Aerobic Threshold Assessment:</span>
                <span className="font-semibold text-gray-200">
                  {activity.aerobic_decoupling_pct !== undefined && activity.aerobic_decoupling_pct !== null ? (
                    activity.aerobic_decoupling_pct <= 3.0 ? (
                      <span className="text-emerald-400">Elite aerobic efficiency / zero cardiac fatigue</span>
                    ) : activity.aerobic_decoupling_pct <= 5.0 ? (
                      <span className="text-teal-300">Well-trained aerobic base capacity</span>
                    ) : (
                      <span className="text-amber-400">Heart rate drifted faster than pace (fatigue/heat)</span>
                    )
                  ) : (
                    'Run was under 20 mins or variable interval'
                  )}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* HR Zone Distribution */}
        <div className="bg-gray-900/90 backdrop-blur border border-gray-800 rounded-2xl p-5 shadow-lg">
          <h2 className="text-base font-bold text-white pb-3 border-b border-gray-800">
            Heart Rate Zone Distribution
          </h2>
          {hrZonesData.length === 0 ? (
            <div className="h-44 flex items-center justify-center text-gray-500 text-xs">
              No heart rate series recorded for this session.
            </div>
          ) : (
            <div className="h-52 w-full mt-3">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={hrZonesData} layout="vertical" margin={{ top: 5, right: 30, left: 40, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" horizontal={false} />
                  <XAxis type="number" stroke="#64748b" tick={{ fontSize: 11 }} unit="m" />
                  <YAxis type="category" dataKey="zone" stroke="#94a3b8" tick={{ fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '0.75rem', fontSize: '12px' }}
                    formatter={(val) => [`${val} minutes`, 'Duration']}
                  />
                  <Bar dataKey="minutes" fill="#06b6d4" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>

      {/* 1 KM Splits Breakdown Table */}
      {activity.splits && activity.splits.length > 0 && (
        <div className="bg-gray-900/90 backdrop-blur border border-gray-800 rounded-2xl overflow-hidden shadow-lg">
          <div className="p-4 sm:p-5 border-b border-gray-800">
            <h2 className="text-base font-bold text-white">Kilometer Splits Breakdown</h2>
            <p className="text-xs text-gray-400 mt-0.5">Pace, Grade-Adjusted Pace, HR, and Efficiency per split</p>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-gray-950/60 text-gray-400 uppercase font-semibold border-b border-gray-800">
                <tr>
                  <th className="py-3 px-4">Split</th>
                  <th className="py-3 px-4">Distance</th>
                  <th className="py-3 px-4">Time</th>
                  <th className="py-3 px-4">Actual Pace</th>
                  <th className="py-3 px-4">GAP Pace</th>
                  <th className="py-3 px-4">Avg HR</th>
                  <th className="py-3 px-4">Cadence</th>
                  <th className="py-3 px-4">Elev +/-</th>
                  <th className="py-3 px-4">Efficiency (EF)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {activity.splits.map((split) => (
                  <tr key={split.split_number} className="hover:bg-gray-800/40 transition">
                    <td className="py-3 px-4 font-bold text-white">KM {split.split_number}</td>
                    <td className="py-3 px-4 text-gray-300">{(split.distance_meters / 1000).toFixed(2)} km</td>
                    <td className="py-3 px-4 text-gray-300">{formatDuration(split.elapsed_time_sec)}</td>
                    <td className="py-3 px-4 font-mono font-bold text-cyan-400">{formatPace(split.pace_sec_km)}</td>
                    <td className="py-3 px-4 font-mono font-bold text-teal-300">{formatPace(split.gap_sec_km)}</td>
                    <td className="py-3 px-4 text-rose-400 font-semibold">{split.avg_hr ? `${split.avg_hr} bpm` : '--'}</td>
                    <td className="py-3 px-4 text-violet-400">{split.avg_cadence ? `${Math.round(split.avg_cadence)} spm` : '--'}</td>
                    <td className="py-3 px-4 text-gray-300">
                      {split.elevation_diff_m === null || split.elevation_diff_m === undefined
                        ? '--'
                        : split.elevation_diff_m > 0
                        ? `+${split.elevation_diff_m}m`
                        : `${split.elevation_diff_m}m`}
                    </td>
                    <td className="py-3 px-4 text-gray-300 font-semibold">{split.aerobic_efficiency || '--'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Best Efforts Achieved in this Activity */}
      {activity.best_efforts && activity.best_efforts.length > 0 && (
        <div className="bg-gray-900/90 backdrop-blur border border-gray-800 rounded-2xl p-5 shadow-lg">
          <div className="flex items-center space-x-2 pb-3 border-b border-gray-800">
            <Award className="w-5 h-5 text-amber-400" />
            <h2 className="text-base font-bold text-white">Best Efforts in this Workout</h2>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3 mt-4">
            {activity.best_efforts.map((effort, idx) => (
              <div key={idx} className="bg-gray-950 p-3 rounded-xl border border-gray-800 relative">
                {effort.is_personal_record && (
                  <span className="absolute top-2 right-2 px-1.5 py-0.5 rounded text-[9px] font-black bg-amber-500/20 text-amber-400 border border-amber-500/40 uppercase tracking-wider">
                    PR
                  </span>
                )}
                <span className="text-xs font-bold text-gray-400 block">{effort.label}</span>
                <span className="text-base font-black text-white block mt-1 font-mono">{formatDuration(effort.time_seconds)}</span>
                <span className="text-[10px] text-cyan-400 font-mono block mt-0.5">{formatPace(effort.pace_sec_km)} /km</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

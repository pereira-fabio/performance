import React from 'react';
import { Activity } from '../types';
import { MapContainer, TileLayer, Polyline } from 'react-leaflet';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts';
import { pace, duration, km, dateLabel, timeLabel, bucketOf, SPORTS, whyMissing } from '../lib/format';
import { Stat, StatGrid, Section, Empty, Card } from './Stat';

interface Props {
  activity: Activity;
  onBack: () => void;
  onDelete: (id: string) => void;
}

/** A dash the reader can interrogate: hovering says why the figure is absent. */
const Missing: React.FC<{ reason?: string }> = ({ reason }) => (
  <span className="text-faint cursor-help" title={reason ?? 'Not recorded'}>—</span>
);

export const ActivityDetail: React.FC<Props> = ({ activity, onBack, onDelete }) => {
  const bucket = bucketOf(activity);
  const showPace = SPORTS[bucket].hasPace;
  const points = activity.stream_data?.points ?? [];
  const route = points.filter((p) => p.lat != null && p.lng != null)
                      .map((p) => [p.lat!, p.lng!] as [number, number]);

  const series = points
    .filter((p) => p.heart_rate != null || p.speed != null)
    .map((p) => ({
      km: Number(((p.distance ?? 0) / 1000).toFixed(2)),
      min: Math.round((p.timestamp_offset ?? 0) / 60),
      hr: p.heart_rate ?? null,
      pace: p.speed && p.speed > 0.5 ? Math.min(1000 / p.speed, 900) : null,
    }));

  const zones = activity.hr_zone_seconds
    ? Object.entries(activity.hr_zone_seconds).filter(([, v]) => v > 0)
    : [];
  const zoneTotal = zones.reduce((s, [, v]) => s + v, 0);
  const splits = (activity.splits ?? []).filter((s) => !s.is_partial);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <button onClick={onBack} className="text-[13px] text-muted hover:text-fg transition">← Back</button>
        <button onClick={() => { if (confirm('Delete this activity?')) onDelete(activity.id); }}
                className="text-2xs text-faint hover:text-negative transition">Delete</button>
      </div>

      <div className="flex items-baseline gap-2 mb-1">
        <span className="h-2 w-2 rounded-full" style={{ background: SPORTS[bucket].color }} />
        <h2 className="text-xl font-semibold tracking-tight text-fg-strong">{activity.name}</h2>
      </div>
      <p className="text-[13px] text-muted tnum mb-2">
        {dateLabel(activity.start_time)} · {timeLabel(activity.start_time)} · {activity.sport_type}
      </p>

      {/* Coverage is stated rather than assumed: a metric computed from 40% of
          a session should be read differently from one computed from 98%. */}
      {activity.hr_coverage != null && activity.hr_coverage < 0.8 && (
        <p className="text-2xs text-caution mb-2">
          Heart rate covers {Math.round(activity.hr_coverage * 100)}% of this session — derived
          figures are limited accordingly.
        </p>
      )}

      <Card className="mt-4"><StatGrid cols={4}>
        {showPace
          ? <Stat label="Distance" value={km(activity.distance_meters)} unit="km"
                  title={whyMissing(activity, 'distance')} />
          : <Stat label="Duration" value={duration(activity.moving_time_sec)} />}
        {showPace
          ? <Stat label="Pace" value={pace(activity.avg_pace_sec_km)} unit="/km" />
          : <Stat label="Avg HR" value={activity.avg_hr ?? <Missing />} unit={activity.avg_hr ? 'bpm' : ''} />}
        <Stat label={showPace ? 'Moving' : 'Load'}
              value={showPace ? duration(activity.moving_time_sec) : Math.round(activity.r_tss ?? 0)} />
        <Stat label={showPace ? 'Avg HR' : 'Max HR'}
              value={(showPace ? activity.avg_hr : activity.max_hr) ?? <Missing />}
              unit={(showPace ? activity.avg_hr : activity.max_hr) ? 'bpm' : ''} />
      </StatGrid></Card>

      {showPace && (
        <Card className="mt-4"><StatGrid cols={4}>
          <Stat label="GAP" value={activity.gap_pace_sec_km ? pace(activity.gap_pace_sec_km) : <Missing reason={whyMissing(activity, 'gap_pace')} />}
                unit={activity.gap_pace_sec_km ? '/km' : ''} />
          <Stat label="Ascent"
                value={activity.elevation_gain_m != null ? Math.round(activity.elevation_gain_m) : <Missing reason={whyMissing(activity, 'elevation')} />}
                unit={activity.elevation_gain_m != null ? 'm' : ''} />
          <Stat label="Decoupling"
                value={activity.aerobic_decoupling_pct != null ? `${activity.aerobic_decoupling_pct}%` : <Missing reason={whyMissing(activity, 'aerobic_decoupling')} />}
                tone={activity.aerobic_decoupling_pct != null && activity.aerobic_decoupling_pct > 5 ? 'caution' : 'default'} />
          <Stat label="Load" value={Math.round(activity.r_tss ?? 0)}
                sub={activity.data_quality?.rtss_basis === 'banister_trimp_fallback' ? 'from heart rate' : undefined} />
        </StatGrid></Card>
      )}

      {route.length > 1 && (
        <Section title="Route">
          <div className="h-64 rounded-lg overflow-hidden border border-line">
            <MapContainer bounds={route as any} style={{ height: '100%', width: '100%' }}
                          scrollWheelZoom={false} attributionControl={false}>
              <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
              <Polyline positions={route} pathOptions={{ color: SPORTS[bucket].color, weight: 3 }} />
            </MapContainer>
          </div>
        </Section>
      )}

      {series.length > 10 && (
        <Section title="Heart rate">
          <div className="h-40 -ml-3">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={series} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id="hrFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--negative)" stopOpacity={0.25} />
                    <stop offset="100%" stopColor="var(--negative)" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="var(--line)" vertical={false} />
                <XAxis dataKey={showPace ? 'km' : 'min'} tickLine={false} axisLine={false}
                       tick={{ fontSize: 10, fill: 'var(--faint)' }} minTickGap={40}
                       tickFormatter={(v) => `${v}${showPace ? 'km' : 'm'}`} />
                <YAxis domain={['dataMin - 10', 'dataMax + 10']} tickLine={false} axisLine={false}
                       width={32} tick={{ fontSize: 10, fill: 'var(--faint)' }} />
                <Tooltip contentStyle={{
                  background: 'var(--bg)', border: '1px solid var(--line-strong)',
                  borderRadius: 8, fontSize: 12, color: 'var(--fg)',
                }} />
                <Area type="monotone" dataKey="hr" stroke="var(--negative)" strokeWidth={1.5}
                      fill="url(#hrFill)" connectNulls dot={false} name="bpm" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </Section>
      )}

      {zones.length > 0 && (
        <Section title="Time in heart-rate zones">
          <div className="flex h-2 rounded-full overflow-hidden mb-3">
            {zones.map(([z, v], i) => (
              <div key={z} title={`${z.toUpperCase()} · ${duration(v)}`}
                   style={{ width: `${(v / zoneTotal) * 100}%`, background: SPORTS[bucket].color,
                            opacity: 0.3 + (i / zones.length) * 0.7 }} />
            ))}
          </div>
          <div className="grid grid-cols-5 gap-2 text-2xs tnum">
            {zones.map(([z, v]) => (
              <div key={z}>
                <div className="text-faint">{z.toUpperCase()}</div>
                <div className="text-fg">{duration(v)}</div>
              </div>
            ))}
          </div>
        </Section>
      )}

      {showPace && splits.length > 0 && (
        <Section title="Splits">
          <table className="w-full text-[13px] tnum">
            <thead>
              <tr className="text-2xs text-faint text-left">
                <th className="font-normal pb-2">Km</th>
                <th className="font-normal pb-2 text-right">Pace</th>
                <th className="font-normal pb-2 text-right hidden sm:table-cell">GAP</th>
                <th className="font-normal pb-2 text-right">HR</th>
                <th className="font-normal pb-2 text-right hidden sm:table-cell">Elev</th>
              </tr>
            </thead>
            <tbody>
              {splits.map((s) => (
                <tr key={s.split_number} className="border-t border-line">
                  <td className="py-1.5 text-muted">{s.split_number}</td>
                  <td className="py-1.5 text-right text-fg-strong">{pace(s.pace_sec_km)}</td>
                  <td className="py-1.5 text-right text-muted hidden sm:table-cell">{s.gap_sec_km ? pace(s.gap_sec_km) : '—'}</td>
                  <td className="py-1.5 text-right text-muted">{s.avg_hr ?? '—'}</td>
                  <td className="py-1.5 text-right text-muted hidden sm:table-cell">
                    {s.elevation_diff_m != null ? `${s.elevation_diff_m > 0 ? '+' : ''}${Math.round(s.elevation_diff_m)}m` : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}

      {!showPace && series.length <= 10 && zones.length === 0 && (
        <Empty>This session recorded heart rate only — no route, pace or distance.</Empty>
      )}
    </div>
  );
};

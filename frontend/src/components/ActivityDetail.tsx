import React, { useEffect, useMemo, useState } from 'react';
import { Activity, StreamPoint, Split } from '../types';
import { MapContainer, TileLayer, Polyline, CircleMarker, Tooltip as MapTooltip } from 'react-leaflet';
import {
  ResponsiveContainer, ComposedChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts';
import { pace, duration, km, dateLabel, timeLabel, bucketOf, SPORTS, whyMissing } from '../lib/format';
import { Stat, StatGrid, Section, Empty, Card } from './Stat';
import { CoachNoteCard } from './CoachNote';

const TE_LABEL = (te?: number) =>
  te == null ? '' : te < 1.5 ? 'Easy' : te < 2.5 ? 'Maintaining'
    : te < 3.5 ? 'Improving' : te < 4.5 ? 'Highly improving' : 'Overreaching';

/**
 * Zones, coloured as a progression rather than as one colour at several
 * opacities. A faded tint of the sport colour was almost invisible against the
 * card, which defeats the point of a chart.
 *
 * Six entries because pace has six zones where heart rate has five. Both run
 * easiest to hardest, so the same ramp reads correctly for either.
 */
const ZONE_COLORS = ['var(--walk)', 'var(--positive)', 'var(--caution)',
                     'var(--accent)', 'var(--negative)', 'var(--gym)'];

const HR_ZONE_NAMES = ['Recovery', 'Aerobic', 'Tempo', 'Threshold', 'Maximum'];

// Pace zones are defined against threshold pace, so they carry the names that
// go with it rather than the heart-rate ones.
const PACE_ZONE_NAMES = ['Recovery', 'Endurance', 'Tempo', 'Threshold',
                         'VO\u2082 max', 'Anaerobic'];

interface Props {
  activity: Activity;
  onBack: () => void;
  onDelete: (id: string) => void;
}

/**
 * The route, drawn from start to finish.
 *
 * The whole line is laid down faintly first so the shape and the map bounds
 * are right immediately, and the bright trace is drawn over it -- a blank map
 * that fills in slowly is worse than a map you can read at once.
 *
 * Timed rather than stepped per point, so a 400-point walk and a 2000-point
 * marathon take the same couple of seconds. Anyone who has asked their system
 * for less motion gets the finished line and no animation at all.
 */
const AnimatedRoute: React.FC<{
  route: [number, number][];
  color: string;
  activityId: string;
}> = ({ route, color, activityId }) => {
  const [drawn, setDrawn] = useState(route.length);

  useEffect(() => {
    const reduced = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    if (reduced || route.length < 3) {
      setDrawn(route.length);
      return;
    }
    setDrawn(0);
    let frame = 0;
    const started = performance.now();
    const DURATION = 1800;
    const step = (now: number) => {
      const t = Math.min(1, (now - started) / DURATION);
      // Eased out, so the pen arrives rather than stopping dead.
      const eased = 1 - Math.pow(1 - t, 3);
      setDrawn(Math.max(2, Math.round(eased * route.length)));
      if (t < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [activityId, route.length]);

  const done = drawn >= route.length;
  const start = route[0];
  const finish = route[route.length - 1];

  return (
    <>
      <Polyline positions={route}
                pathOptions={{ color, weight: 4, opacity: 0.18 }} />
      <Polyline positions={route.slice(0, drawn)}
                pathOptions={{ color, weight: 4, lineCap: 'round', lineJoin: 'round' }} />

      <CircleMarker center={start} radius={6}
                    pathOptions={{ color: '#fff', weight: 2.5,
                                   fillColor: 'var(--positive)', fillOpacity: 1 }}>
        <MapTooltip direction="top">Start</MapTooltip>
      </CircleMarker>

      {/* The finish appears when the line reaches it, so the marker means
          "here" rather than sitting there through the whole animation. */}
      {done && (
        <CircleMarker center={finish} radius={6}
                      pathOptions={{ color: '#fff', weight: 2.5,
                                     fillColor: 'var(--negative)', fillOpacity: 1 }}>
          <MapTooltip direction="top">Finish</MapTooltip>
        </CircleMarker>
      )}
    </>
  );
};

/** A dash the reader can interrogate: hovering says why the figure is absent. */
const Missing: React.FC<{ reason?: string }> = ({ reason }) => (
  <span className="text-faint cursor-help" title={reason ?? 'Not recorded'}>—</span>
);

/**
 * A rolling mean.
 *
 * Applied to pace and elevation, never to heart rate. Speed derived from GPS
 * jumps around far more than the runner did, so the raw trace shows the
 * receiver's noise rather than the effort. Heart rate arrives already smooth
 * from the strap, and averaging a real measurement would only misrepresent it.
 */
const smooth = (values: (number | null)[], window = 5): (number | null)[] => {
  const half = Math.floor(window / 2);
  return values.map((value, i) => {
    if (value == null) return null;
    let sum = 0;
    let count = 0;
    for (let j = Math.max(0, i - half); j <= Math.min(values.length - 1, i + half); j++) {
      const v = values[j];
      if (v != null) { sum += v; count++; }
    }
    return count ? sum / count : null;
  });
};

const clock = (sec?: number | null): string => {
  if (!sec || sec <= 0) return '—';
  const total = Math.round(sec);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  return h > 0 ? `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
               : `${m}:${String(s).padStart(2, '0')}`;
};

type Metric = 'hr' | 'pace';

interface ChartRow {
  km: number;
  min: number;
  hr: number | null;
  pace: number | null;
  elevation: number | null;
}

/**
 * One chart, switched between heart rate and pace.
 *
 * Two charts stacked would double the height for the same axis; switching
 * keeps the trace large enough to read. Elevation sits behind both because the
 * hill is the reason for most of what either trace does -- reading a pace
 * chart without it invites blaming the runner for a climb.
 */
const MetricChart: React.FC<{
  rows: ChartRow[];
  activity: Activity;
  showPace: boolean;
  fastestSplit?: Split;
}> = ({ rows, activity, showPace, fastestSplit }) => {
  const hasHr = rows.some((r) => r.hr != null);
  const hasPace = showPace && rows.some((r) => r.pace != null);
  const hasElevation = rows.some((r) => r.elevation != null);

  const [metric, setMetric] = useState<Metric>(hasHr ? 'hr' : 'pace');
  const active: Metric = (metric === 'hr' && !hasHr) ? 'pace'
                       : (metric === 'pace' && !hasPace) ? 'hr' : metric;

  if (!hasHr && !hasPace) return null;

  const paceValues = rows.map((r) => r.pace).filter((p): p is number => p != null);
  const isPace = active === 'pace';
  const color = isPace ? 'var(--run)' : 'var(--negative)';

  return (
    <Section title={isPace ? 'Pace' : 'Heart rate'}
             aside={hasHr && hasPace ? (
               <div className="flex gap-1 p-0.5 rounded-lg bg-surface border border-line">
                 {(['hr', 'pace'] as Metric[]).map((m) => (
                   <button key={m} onClick={() => setMetric(m)}
                     className={`px-2.5 py-1 rounded-md text-2xs font-semibold transition ${
                       active === m ? 'bg-card text-fg-strong shadow-card' : 'text-muted hover:text-fg'}`}>
                     {m === 'hr' ? 'Heart rate' : 'Pace'}
                   </button>
                 ))}
               </div>
             ) : undefined}>
      {/* The figures that belong to whichever trace is showing, so switching
          changes the whole answer rather than just the line. */}
      <div className="flex flex-wrap gap-x-8 gap-y-3 mb-4">
        {isPace ? (
          <>
            <Stat label="Average" value={pace(activity.avg_pace_sec_km)} unit="/km" />
            <Stat label="Moving" value={duration(activity.moving_time_sec)} />
            <Stat label="Fastest split"
                  value={fastestSplit ? pace(fastestSplit.pace_sec_km) : <Missing />}
                  unit={fastestSplit ? '/km' : ''}
                  sub={fastestSplit ? `kilometre ${fastestSplit.split_number}` : undefined} />
          </>
        ) : (
          <>
            <Stat label="Average" value={activity.avg_hr ?? <Missing />}
                  unit={activity.avg_hr ? 'bpm' : ''} />
            <Stat label="Maximum" value={activity.max_hr ?? <Missing />}
                  unit={activity.max_hr ? 'bpm' : ''} />
            {activity.min_hr != null && (
              <Stat label="Lowest" value={activity.min_hr} unit="bpm" />
            )}
          </>
        )}
      </div>

      <div className="h-52 -ml-3">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={rows} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
            <defs>
              <linearGradient id="metricFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.28} />
                <stop offset="100%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="var(--line)" vertical={false} />
            <XAxis dataKey={showPace ? 'km' : 'min'} tickLine={false} axisLine={false}
                   tick={{ fontSize: 10, fill: 'var(--faint)' }} minTickGap={40}
                   tickFormatter={(v) => `${v}${showPace ? 'km' : 'm'}`} />

            {/* Elevation keeps its own scale and its own axis on the right, so
                the hill never distorts the trace in front of it. */}
            {hasElevation && (
              <YAxis yAxisId="elevation" orientation="right" width={34}
                     domain={['dataMin - 5', 'dataMax + 20']}
                     tickLine={false} axisLine={false}
                     tick={{ fontSize: 10, fill: 'var(--faint)' }}
                     tickFormatter={(v) => `${Math.round(v)}m`} />
            )}
            <YAxis yAxisId="metric" width={38} tickLine={false} axisLine={false}
                   tick={{ fontSize: 10, fill: 'var(--faint)' }}
                   // Faster is a smaller number, so the pace axis is flipped:
                   // a rising line has to mean a better effort.
                   reversed={isPace}
                   domain={isPace
                     ? [Math.max(0, Math.min(...paceValues) - 20), Math.max(...paceValues) + 20]
                     : ['dataMin - 10', 'dataMax + 10']}
                   tickFormatter={(v) => (isPace ? pace(v) : String(Math.round(v)))} />

            <Tooltip contentStyle={{
              background: 'var(--bg)', border: '1px solid var(--line-strong)',
              borderRadius: 8, fontSize: 12, color: 'var(--fg)',
            }}
              labelFormatter={(v) => `${v}${showPace ? ' km' : ' min'}`}
              formatter={(value: number, name: string) => {
                if (name === 'Elevation') return [`${Math.round(value)} m`, name];
                return isPace ? [`${pace(value)} /km`, 'Pace'] : [`${Math.round(value)} bpm`, 'Heart rate'];
              }} />

            {hasElevation && (
              <Area yAxisId="elevation" type="monotone" dataKey="elevation"
                    stroke="none" fill="var(--line-strong)" fillOpacity={0.5}
                    connectNulls dot={false} isAnimationActive={false} name="Elevation" />
            )}
            <Area yAxisId="metric" type="monotone" dataKey={active}
                  stroke={color} strokeWidth={1.75} fill="url(#metricFill)"
                  connectNulls dot={false} isAnimationActive={false}
                  name={isPace ? 'Pace' : 'Heart rate'} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      {isPace && (
        <p className="mt-3 pt-3 border-t border-line text-2xs text-faint">
          Pace is smoothed over a few seconds. Speed from GPS jumps around more than the
          runner does, and the raw trace shows the receiver rather than the effort.
        </p>
      )}
    </Section>
  );
};

/** Zones stacked one per row, so the shortest is still legible. */
const ZoneBars: React.FC<{
  zones: [string, number][]; total: number; names: string[];
}> = ({ zones, total, names }) => (
  <div className="space-y-2.5">
    {zones.map(([zone, seconds]) => {
      const share = total > 0 ? (seconds / total) * 100 : 0;
      // Indexed by the zone's own number, never by its position in the list.
      // Zones with no time are dropped, so a hard session with nothing in Z1
      // would otherwise paint Z2 in the recovery colour and shift every label
      // up with it.
      const index = (parseInt(zone.replace(/\D/g, ''), 10) || 1) - 1;
      const color = ZONE_COLORS[index] ?? ZONE_COLORS[ZONE_COLORS.length - 1];
      return (
        <div key={zone} className="flex items-center gap-3">
          <div className="w-20 shrink-0">
            <div className="text-xs font-semibold text-fg-strong">{zone.toUpperCase()}</div>
            <div className="text-2xs text-faint">{names[index] ?? ''}</div>
          </div>
          <div className="flex-1 h-6 rounded bg-surface overflow-hidden">
            <div className="h-full rounded transition-all"
                 style={{ width: `${Math.max(share, 0.8)}%`, background: color }} />
          </div>
          <div className="w-24 shrink-0 text-right">
            <div className="text-xs font-semibold tnum text-fg-strong">{duration(seconds)}</div>
            <div className="text-2xs text-faint tnum">{share.toFixed(0)}%</div>
          </div>
        </div>
      );
    })}
  </div>
);

type ZoneKind = 'hr' | 'pace';

/**
 * Time in zones, by heart rate or by pace.
 *
 * The same session read two ways: heart rate says what it cost, pace says what
 * was asked of the legs. They disagree usefully -- a hilly run sits high in the
 * heart-rate zones and low in the pace ones -- so they are one section with a
 * switch rather than two sections nobody compares.
 */
const ZoneSection: React.FC<{
  hr: [string, number][];
  paceZones: [string, number][];
}> = ({ hr, paceZones }) => {
  const [kind, setKind] = useState<ZoneKind>(hr.length ? 'hr' : 'pace');
  const active: ZoneKind = kind === 'hr' && !hr.length ? 'pace'
                         : kind === 'pace' && !paceZones.length ? 'hr' : kind;

  const zones = active === 'hr' ? hr : paceZones;
  if (!zones.length) return null;
  const total = zones.reduce((sum, [, v]) => sum + v, 0);

  return (
    <Section
      title="Time in zones"
      aside={
        <div className="flex items-center gap-3">
          {hr.length > 0 && paceZones.length > 0 && (
            <div className="flex gap-1 p-0.5 rounded-lg bg-surface border border-line">
              {([['hr', 'Heart rate'], ['pace', 'Pace']] as [ZoneKind, string][]).map(
                ([value, label]) => (
                  <button key={value} onClick={() => setKind(value)}
                    className={`px-2.5 py-1 rounded-md text-2xs font-semibold transition ${
                      active === value ? 'bg-card text-fg-strong shadow-card'
                                       : 'text-muted hover:text-fg'}`}>
                    {label}
                  </button>
                )
              )}
            </div>
          )}
          <span className="text-2xs text-faint tnum">{duration(total)}</span>
        </div>
      }>
      <ZoneBars zones={zones} total={total}
                names={active === 'hr' ? HR_ZONE_NAMES : PACE_ZONE_NAMES} />
      <p className="mt-4 pt-3 border-t border-line text-2xs text-faint">
        {active === 'hr'
          ? 'From your maximum, resting and threshold heart rates. Totals cover measured time, not elapsed time.'
          : 'From your threshold pace. A climb shows here as an easy zone and in the heart-rate zones as a hard one, which is the hill rather than a contradiction.'}
      </p>
    </Section>
  );
};

/**
 * Splits as bars.
 *
 * Length is proportional to speed rather than to time, so the longest bar is
 * the quickest kilometre. A bar drawn from the pace number would make the
 * slowest split the biggest thing on the page, which reads as an achievement.
 */
const SplitBars: React.FC<{ splits: Split[]; color: string }> = ({ splits, color }) => {
  const quickest = Math.min(...splits.map((s) => s.pace_sec_km));
  const slowest = Math.max(...splits.map((s) => s.pace_sec_km));
  return (
    <div className="space-y-1.5">
      {splits.map((s) => {
        // Scaled against the quickest split, with a floor so the slowest
        // kilometre of a long run is still a bar and not a sliver.
        const width = 30 + (quickest / s.pace_sec_km) * 70;
        return (
          <div key={s.split_number} className="flex items-center gap-3 text-[13px] tnum">
            <span className="w-5 shrink-0 text-2xs text-faint text-right">{s.split_number}</span>
            <div className="flex-1 h-7 rounded bg-surface overflow-hidden relative">
              {/* One colour throughout. Length already says which split was
                  quickest; shading it as well said the same thing twice. */}
              <div className="h-full rounded flex items-center px-2"
                   style={{ width: `${width}%`, background: color }}>
                <span className="text-2xs font-semibold text-white drop-shadow">
                  {pace(s.pace_sec_km)}
                </span>
              </div>
            </div>
            <span className="w-10 shrink-0 text-right text-2xs text-muted">
              {s.avg_hr ?? '—'}
            </span>
            <span className="w-12 shrink-0 text-right text-2xs text-muted hidden sm:inline">
              {s.elevation_diff_m != null
                ? `${s.elevation_diff_m > 0 ? '+' : ''}${Math.round(s.elevation_diff_m)}m`
                : '—'}
            </span>
          </div>
        );
      })}
      <div className="flex items-center gap-3 pt-1 text-2xs text-faint">
        <span className="w-5 shrink-0" />
        <span className="flex-1">
          {splits.length > 1 && `${pace(quickest)} to ${pace(slowest)} per km`}
        </span>
        <span className="w-10 shrink-0 text-right">bpm</span>
        <span className="w-12 shrink-0 text-right hidden sm:inline">elev</span>
      </div>
    </div>
  );
};

export const ActivityDetail: React.FC<Props> = ({ activity, onBack, onDelete }) => {
  const bucket = bucketOf(activity);
  const showPace = SPORTS[bucket].hasPace;
  const points: StreamPoint[] = activity.stream_data?.points ?? [];
  const route = points.filter((p) => p.lat != null && p.lng != null)
                      .map((p) => [p.lat!, p.lng!] as [number, number]);

  const rows: ChartRow[] = useMemo(() => {
    const kept = points.filter(
      (p) => p.heart_rate != null || p.speed != null || p.altitude != null
    );
    // Smoothed as whole series first, so the window spans neighbours in time
    // rather than whatever survived a per-point filter.
    const paces = smooth(kept.map((p) => (p.speed && p.speed > 0.5 ? Math.min(1000 / p.speed, 900) : null)));
    const elevations = smooth(kept.map((p) => p.altitude ?? null));
    return kept.map((p, i) => ({
      km: Number(((p.distance ?? 0) / 1000).toFixed(2)),
      min: Math.round((p.timestamp_offset ?? 0) / 60),
      hr: p.heart_rate ?? null,
      pace: paces[i],
      elevation: elevations[i],
    }));
  }, [points]);

  // Sorted by zone key so z10 could never sort before z2, and so the colour
  // ramp always lines up with the order the zones are defined in.
  const asZones = (source?: Record<string, number> | null): [string, number][] =>
    source
      ? (Object.entries(source) as [string, number][])
          .filter(([, v]) => v > 0)
          .sort((a, b) => a[0].localeCompare(b[0], undefined, { numeric: true }))
      : [];
  const hrZones = asZones(activity.hr_zone_seconds);
  const paceZones = showPace ? asZones(activity.pace_zone_seconds) : [];
  const splits = (activity.splits ?? []).filter((s) => !s.is_partial);
  const fastestSplit = splits.length
    ? splits.reduce((best, s) => (s.pace_sec_km < best.pace_sec_km ? s : best))
    : undefined;

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

      {/* The map leads: it is the one thing that says at a glance which run
          this was, before any number does. */}
      {route.length > 1 && (
        <Section title="Route" flush>
          <div className="h-72 rounded-xl overflow-hidden">
            {/* Keyed on the activity: Leaflet holds onto its container, and
                reusing one across activities leaves the previous route drawn. */}
            <MapContainer key={activity.id} bounds={route as any}
                          style={{ height: '100%', width: '100%' }}
                          scrollWheelZoom={false} attributionControl={false}>
              <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
              <AnimatedRoute route={route} color={SPORTS[bucket].color}
                             activityId={activity.id} />
            </MapContainer>
          </div>
        </Section>
      )}

      {showPace && splits.length > 0 && (
        <Section title="Splits"
                 aside={<span className="text-2xs text-faint">longest bar is quickest</span>}>
          <SplitBars splits={splits} color={SPORTS[bucket].color} />
        </Section>
      )}

      {rows.length > 10 && (
        <MetricChart rows={rows} activity={activity} showPace={showPace}
                     fastestSplit={fastestSplit} />
      )}

      <ZoneSection hr={hrZones} paceZones={paceZones} />

      <CoachNoteCard activityId={activity.id} title="Coach's note" />

      {/* Effort: what the session cost and what it is likely to have built.
          Both are modelled from load, and say so. */}
      <Section title="Effort">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-5">
          <Stat label="Training effect"
                value={activity.training_effect_aerobic ?? <Missing reason={whyMissing(activity, 'training_effect')} />}
                sub={TE_LABEL(activity.training_effect_aerobic) || undefined}
                tone="accent" />
          <Stat label="Anaerobic"
                value={activity.training_effect_anaerobic ?? <Missing />}
                sub={TE_LABEL(activity.training_effect_anaerobic) || undefined} />
          <Stat label="Recovery"
                value={activity.recovery_hours ?? <Missing reason={whyMissing(activity, 'recovery')} />}
                unit={activity.recovery_hours ? 'h' : ''} sub="until absorbed" />
          <Stat label="Experience" value={activity.xp ?? 0} unit="xp" />
        </div>
        <p className="mt-4 pt-3 border-t border-line text-xs text-muted">
          Training effect and recovery are estimated from training load relative to your
          current fitness, not measured directly.
        </p>
      </Section>

      <Section title="Details">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-5">
          {showPace && (
            <Stat label="GAP" value={activity.gap_pace_sec_km ? pace(activity.gap_pace_sec_km) : <Missing reason={whyMissing(activity, 'gap_pace')} />}
                  unit={activity.gap_pace_sec_km ? '/km' : ''} sub="grade-adjusted" />
          )}
          {showPace && (
            <Stat label="Ascent"
                  value={activity.elevation_gain_m != null ? Math.round(activity.elevation_gain_m) : <Missing reason={whyMissing(activity, 'elevation')} />}
                  unit={activity.elevation_gain_m != null ? 'm' : ''} />
          )}
          {showPace && (
            <Stat label="Decoupling"
                  value={activity.aerobic_decoupling_pct != null ? `${activity.aerobic_decoupling_pct}%` : <Missing reason={whyMissing(activity, 'aerobic_decoupling')} />}
                  tone={activity.aerobic_decoupling_pct != null && activity.aerobic_decoupling_pct > 5 ? 'caution' : 'default'}
                  sub="under 5% is well paced" />
          )}
          <Stat label="Load" value={Math.round(activity.r_tss ?? 0)}
                sub={activity.data_quality?.rtss_basis === 'banister_trimp_fallback' ? 'from heart rate' : undefined} />
          {showPace && (
            <Stat label="Fastest" value={activity.max_speed_mps ? pace(1000 / activity.max_speed_mps) : <Missing />}
                  unit={activity.max_speed_mps ? '/km' : ''} sub="best 30 seconds" />
          )}
          <Stat label="Calories" value={activity.calories_kcal ? Math.round(activity.calories_kcal) : <Missing reason="Not written by the device for this session" />}
                unit={activity.calories_kcal ? 'kcal' : ''} />
          <Stat label="Steps" value={activity.steps ? activity.steps.toLocaleString() : <Missing reason="Not written by the device for this session" />} />
          {showPace && (
            <Stat label="Cadence" value={activity.avg_cadence ? Math.round(activity.avg_cadence) : <Missing reason={whyMissing(activity, 'cadence_series')} />}
                  unit={activity.avg_cadence ? 'spm' : ''}
                  sub={activity.avg_stride_length_m ? `${activity.avg_stride_length_m.toFixed(2)} m stride` : undefined} />
          )}
          <Stat label="VO₂ max" value={activity.vo2_max ? Math.round(activity.vo2_max) : <Missing reason="No VO2 max reading near this session" />} />
        </div>
      </Section>

      {!showPace && rows.length <= 10 && hrZones.length === 0 && (
        <Empty>This session recorded heart rate only — no route, pace or distance.</Empty>
      )}
    </div>
  );
};

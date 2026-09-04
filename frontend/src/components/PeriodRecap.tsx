import React, { useEffect, useMemo, useState } from 'react';
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, Cell, CartesianGrid,
} from 'recharts';
import { PeriodReport, Delta, ReportSession } from '../types';
import { Card, Stat, StatGrid, Section, Empty } from './Stat';
import { PeriodNoteCard } from './CoachNote';
import { downloadReportPdf, getWeekReport, getPeriodReport } from '../api/client';
import { pace, duration, dateLabel } from '../lib/format';
import { describeError } from '../lib/errors';

/**
 * A finished period, read as a whole.
 *
 * The dashboard answers "where am I now"; this answers "what did I just do,
 * and was it more or less than before". So every headline figure carries its
 * change against the period before it -- a 42 km week means nothing until you
 * know the week before was 28.
 */

/** Which direction is an improvement. Some figures have no better direction. */
type Direction = 'up' | 'down' | 'flat';

const DeltaBadge: React.FC<{
  delta?: Delta | null;
  unit?: string;
  direction?: Direction;
  /** Renders the magnitude; the sign is shown as an arrow, never as a minus. */
  render?: (v: number) => string;
}> = ({ delta, unit = '', direction = 'up', render }) => {
  if (!delta || delta.change == null) return null;
  const { change, pct } = delta;
  if (Math.abs(change) < 0.05) {
    return <span className="text-2xs font-medium text-faint">no change</span>;
  }
  const better = direction === 'flat' ? null : direction === 'down' ? change < 0 : change > 0;
  const tone = better == null ? 'text-muted' : better ? 'text-positive' : 'text-caution';
  const size = render ? render(Math.abs(change)) : `${Math.abs(change).toLocaleString(undefined, {
    maximumFractionDigits: 1,
  })}${unit}`;
  return (
    <span className={`text-2xs font-semibold tnum ${tone}`}>
      {change > 0 ? '▲' : '▼'} {size}
      {pct != null && Math.abs(pct) >= 1 && (
        <span className="font-normal text-faint"> · {Math.abs(pct).toFixed(0)}%</span>
      )}
    </span>
  );
};

/** A stat with its change underneath, which is the whole point of a recap. */
const CompareStat: React.FC<{
  label: string; value: React.ReactNode; unit?: string;
  delta?: Delta | null; deltaUnit?: string; direction?: Direction;
  render?: (v: number) => string;
}> = ({ label, value, unit, delta, deltaUnit, direction, render }) => (
  <div>
    <div className="text-xs font-medium uppercase tracking-wide text-faint">{label}</div>
    <div className="mt-1 flex items-baseline gap-1">
      <span className="text-2xl font-bold tnum tracking-tight text-fg-strong">{value}</span>
      {unit && <span className="text-sm font-medium text-muted">{unit}</span>}
    </div>
    <div className="mt-1 h-4">
      <DeltaBadge delta={delta} unit={deltaUnit} direction={direction} render={render} />
    </div>
  </div>
);

const shortDuration = (sec: number): string => {
  const h = Math.floor(sec / 3600);
  const m = Math.round((sec % 3600) / 60);
  return h > 0 ? `${h}h ${m}m` : `${m}m`;
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

const SessionRow: React.FC<{ s: ReportSession; onSelect?: (id: string) => void }> = ({
  s, onSelect,
}) => (
  <button
    onClick={() => onSelect?.(s.id)}
    className="w-full text-left px-5 py-3 flex items-center gap-4 hover:bg-surface transition">
    <div className="w-14 shrink-0">
      <div className="text-xs font-semibold text-fg">{dateLabel(s.start_time).split(' ')[0]}</div>
      <div className="text-2xs text-faint">
        {new Date(s.start_time).toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}
      </div>
    </div>
    <div className="min-w-0 flex-1">
      <div className="text-sm font-semibold text-fg-strong truncate">{s.name}</div>
      <div className="text-xs text-muted tnum">
        {s.is_run && s.km ? `${s.km.toFixed(2)} km · ` : ''}{clock(s.moving_sec)}
        {s.avg_hr ? ` · ${s.avg_hr} bpm` : ''}
      </div>
    </div>
    {s.is_run && s.pace_sec_km && (
      <div className="text-right shrink-0">
        <div className="text-sm font-bold tnum text-fg-strong">{pace(s.pace_sec_km)}</div>
        <div className="text-2xs text-faint">/km</div>
      </div>
    )}
  </button>
);

export const PeriodRecap: React.FC<{
  kind: 'week' | 'month' | 'year';
  onBack: () => void;
  onSelectActivity?: (id: string) => void;
}> = ({ kind, onBack, onSelectActivity }) => {
  const [offset, setOffset] = useState(0);
  const [report, setReport] = useState<PeriodReport | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setBusy(true);
    const fetch = kind === 'week' ? getWeekReport(offset) : getPeriodReport(kind, undefined, offset);
    fetch
      .then((r) => { if (!cancelled) { setReport(r); setError(null); } })
      .catch((e) => { if (!cancelled) setError(describeError(e, 'Could not load the recap')); })
      .finally(() => { if (!cancelled) setBusy(false); });
    return () => { cancelled = true; };
  }, [kind, offset]);

  const chart = useMemo(
    () => (report?.breakdown.rows ?? []).map((r) => ({
      label: r.label, km: r.km ?? 0, load: r.load ?? 0, sessions: r.sessions,
    })),
    [report]
  );

  const savePdf = async () => {
    if (!report) return;
    setSaving(true);
    try {
      await downloadReportPdf(report.kind, report.key);
    } catch (e: any) {
      setError(describeError(e, 'Could not build the PDF'));
    } finally {
      setSaving(false);
    }
  };

  const noun = kind === 'week' ? 'week' : kind === 'month' ? 'month' : 'year';

  if (busy && !report) {
    return <Empty>Reading your {noun}…</Empty>;
  }
  if (error && !report) {
    return (
      <>
        <button onClick={onBack} className="text-sm text-muted hover:text-fg mb-4">← Back</button>
        <Empty>{error}</Empty>
      </>
    );
  }
  if (!report) return null;

  const t = report.totals;
  const d = report.deltas;
  const hasComparison = (report.previous?.totals?.sessions ?? 0) > 0;

  return (
    <>
      <div className="flex items-center justify-between gap-3 mb-5">
        <button onClick={onBack}
                className="text-sm text-muted hover:text-fg transition shrink-0">← Back</button>
        <div className="flex items-center gap-1">
          <button onClick={() => setOffset(offset + 1)} aria-label="Earlier"
                  className="p-1.5 rounded-lg text-muted hover:text-fg hover:bg-surface transition">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth="2" strokeLinecap="round"><path d="M15 18l-6-6 6-6" /></svg>
          </button>
          <button onClick={() => setOffset(Math.max(0, offset - 1))} disabled={offset === 0}
                  aria-label="Later"
                  className="p-1.5 rounded-lg text-muted hover:text-fg hover:bg-surface transition disabled:opacity-30">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth="2" strokeLinecap="round"><path d="M9 18l6-6-6-6" /></svg>
          </button>
        </div>
      </div>

      <div className="flex items-end justify-between gap-4 flex-wrap mb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-fg-strong">{report.label}</h1>
          <p className="mt-0.5 text-sm text-muted">
            {report.complete
              ? `Your ${noun} in full`
              : `This ${noun} is still running, so the figures will keep moving`}
            {hasComparison && ` · compared with ${report.previous.label}`}
          </p>
        </div>
        <button onClick={savePdf} disabled={saving || report.empty}
                className="shrink-0 px-3.5 py-2 text-xs font-semibold rounded-lg border border-line
                           text-muted hover:text-fg hover:border-line-strong transition disabled:opacity-40">
          {saving ? 'Building…' : 'Save as PDF'}
        </button>
      </div>

      {error && (
        <div className="mb-5 py-3 px-4 text-[13px] text-negative border border-line rounded-lg bg-surface">
          {error}
        </div>
      )}

      {report.empty ? (
        <Empty>Nothing was recorded in this {noun}.</Empty>
      ) : (
        <>
          <Card>
            <StatGrid cols={4}>
              <CompareStat label="Distance" value={(t.km ?? 0).toFixed(1)} unit="km"
                           delta={d.km} deltaUnit=" km" />
              <CompareStat label="Time" value={shortDuration(t.moving_sec)}
                           delta={d.moving_sec} render={shortDuration} />
              <CompareStat label="Runs" value={t.runs} delta={d.runs} />
              <CompareStat label="Load" value={Math.round(t.load ?? 0)} delta={d.load} />
            </StatGrid>
          </Card>

          <Section title={`Distance by ${report.breakdown.unit}`}>
            <div className="h-44 -ml-3">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chart} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                  <CartesianGrid vertical={false} stroke="var(--line)" strokeDasharray="3 3" />
                  <XAxis dataKey="label" tickLine={false} axisLine={false}
                         tick={{ fontSize: 11, fill: 'var(--muted)' }}
                         interval={chart.length > 16 ? Math.floor(chart.length / 8) : 0} />
                  <YAxis tickLine={false} axisLine={false} width={34}
                         tick={{ fontSize: 11, fill: 'var(--muted)' }} />
                  <Tooltip
                    cursor={{ fill: 'var(--surface)' }}
                    contentStyle={{
                      background: 'var(--bg)', border: '1px solid var(--line-strong)',
                      borderRadius: 8, fontSize: 12, color: 'var(--fg)',
                    }}
                    formatter={(v: number) => [`${v.toFixed(2)} km`, 'Distance']} />
                  <Bar dataKey="km" radius={[3, 3, 0, 0]} maxBarSize={38}>
                    {chart.map((c, i) => (
                      // A rest day is drawn as an empty slot rather than
                      // dropped: the gaps in a week are part of the picture.
                      <Cell key={i} fill={c.km > 0 ? 'var(--run)' : 'var(--line)'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Section>

          <PeriodNoteCard kind={kind} offset={offset} />

          <Section title="How it compares" flush>
            {hasComparison ? (
              <div className="divide-y divide-line">
                {([
                  ['Days trained', `${t.days_trained} of ${report.day_count}`, d.days_trained, '', 'up'],
                  ['Sessions', String(t.sessions), d.sessions, '', 'up'],
                  ['Elevation', t.elevation_gain_m ? `${Math.round(t.elevation_gain_m)} m` : '—',
                   d.elevation_gain_m, ' m', 'up'],
                  ['Average pace', t.avg_pace_sec_km ? `${pace(t.avg_pace_sec_km)} /km` : '—',
                   d.avg_pace_sec_km, '', 'down'],
                  ['Average heart rate', t.avg_hr ? `${Math.round(t.avg_hr)} bpm` : '—',
                   d.avg_hr, ' bpm', 'flat'],
                  ['Calories', t.calories ? `${Math.round(t.calories).toLocaleString()} kcal` : '—',
                   d.calories, ' kcal', 'up'],
                ] as [string, string, Delta | null, string, Direction][]).map(
                  ([label, value, delta, unit, dir]) => (
                    <div key={label} className="flex items-center justify-between px-5 py-3">
                      <span className="text-[13px] text-muted">{label}</span>
                      <span className="flex items-baseline gap-2.5">
                        <span className="text-sm font-semibold tnum text-fg-strong">{value}</span>
                        <span className="w-24 text-right">
                          <DeltaBadge delta={delta} unit={unit} direction={dir}
                            render={label === 'Average pace'
                              ? (v) => `${Math.round(v)} s/km` : undefined} />
                        </span>
                      </span>
                    </div>
                  )
                )}
              </div>
            ) : (
              <p className="px-5 py-6 text-sm text-muted">
                There is no training recorded in {report.previous.label} to compare against.
              </p>
            )}
          </Section>

          <Section title="The detail">
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-5">
              <Stat label="Longest" value={t.longest_km ? t.longest_km.toFixed(2) : '—'} unit="km" />
              <Stat label="Quickest" value={t.fastest_pace_sec_km ? pace(t.fastest_pace_sec_km) : '—'}
                    unit="/km" sub={t.fastest_name ?? undefined} />
              <Stat label="Grade-adjusted" value={t.avg_gap_sec_km ? pace(t.avg_gap_sec_km) : '—'}
                    unit="/km" sub="average" />
              <Stat label="Cadence" value={t.avg_cadence ? Math.round(t.avg_cadence) : '—'}
                    unit="spm" />
              <Stat label="Stride" value={t.avg_stride_m ? t.avg_stride_m.toFixed(2) : '—'} unit="m" />
              <Stat label="Decoupling" value={t.avg_decoupling_pct != null
                      ? `${t.avg_decoupling_pct.toFixed(1)}%` : '—'}
                    tone={t.avg_decoupling_pct != null && t.avg_decoupling_pct > 5
                      ? 'caution' : 'default'}
                    sub="under 5% is well paced" />
              <Stat label="Fitness" value={report.form.ctl_end != null
                      ? Math.round(report.form.ctl_end) : '—'}
                    tone="accent"
                    sub={report.form.ctl_start != null && report.form.ctl_end != null
                      ? `from ${Math.round(report.form.ctl_start)}` : undefined} />
              <Stat label="Form" value={report.form.tsb_end != null
                      ? Math.round(report.form.tsb_end) : '—'}
                    tone={report.form.tsb_end != null && report.form.tsb_end < -15
                      ? 'caution' : 'default'}
                    sub="fitness minus fatigue" />
            </div>
          </Section>

          {report.records.length > 0 && (
            <Section title="Best efforts" flush>
              <div className="divide-y divide-line">
                {report.records.map((r) => (
                  <div key={r.label} className="flex items-center justify-between px-5 py-3">
                    <span className="flex items-center gap-2">
                      <span className="text-sm font-semibold text-fg-strong">{r.label}</span>
                      {r.is_personal_record && (
                        <span className="text-2xs font-bold uppercase tracking-wide text-accent">
                          personal record
                        </span>
                      )}
                    </span>
                    <span className="flex items-baseline gap-3">
                      <span className="text-sm font-bold tnum text-fg-strong">
                        {clock(r.time_seconds)}
                      </span>
                      <span className="text-xs text-muted tnum w-16 text-right">
                        {pace(r.pace_sec_km)}/km
                      </span>
                    </span>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {Object.keys(report.other_sports).length > 0 && (
            <Section title="Everything else" flush
                     aside={<span className="text-2xs text-faint">not in the running figures</span>}>
              <div className="divide-y divide-line">
                {Object.entries(report.other_sports)
                  .sort((a, b) => b[1].count - a[1].count)
                  .map(([sport, v]) => (
                    <div key={sport} className="flex items-center justify-between px-5 py-3">
                      <span className="text-[13px] capitalize text-fg">{sport}</span>
                      <span className="text-xs text-muted tnum">
                        {v.count} · {v.km > 0 ? `${v.km.toFixed(1)} km · ` : ''}
                        {duration(v.moving_sec)}
                      </span>
                    </div>
                  ))}
              </div>
            </Section>
          )}

          <Section title={`Every session`} flush
                   aside={<span className="text-2xs text-faint tnum">{report.sessions.length}</span>}>
            <div className="divide-y divide-line">
              {report.sessions.map((s) => (
                <SessionRow key={s.id} s={s} onSelect={onSelectActivity} />
              ))}
            </div>
          </Section>
        </>
      )}
    </>
  );
};

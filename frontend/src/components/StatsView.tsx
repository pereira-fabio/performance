import React, { useEffect, useMemo, useState } from 'react';
import {
  ResponsiveContainer, RadarChart, PolarGrid, PolarAngleAxis, Radar,
  PieChart, Pie, Cell, Tooltip,
} from 'recharts';
import { HomeData, PeriodReport, ReportPeriodOption } from '../types';
import { Card, Stat, StatGrid, Section, Empty } from './Stat';
import { ReportBody } from './PeriodRecap';
import { getPeriodReport, getReportPeriods, downloadReportPdf } from '../api/client';
import { describeError } from '../lib/errors';
import { SportKey } from '../lib/format';

/**
 * Everything that describes the long run rather than the current one.
 *
 * The home page is about now -- this week, last week, what is close to being
 * earned. Lifetime totals, the shape of an athlete's training and a report on
 * a month gone by are a different kind of question, asked less often, and they
 * were crowding the answer to the first one.
 */

const ATTRIBUTE_LABELS: Record<string, string> = {
  endurance: 'Endurance',
  speed: 'Speed',
  volume: 'Volume',
  consistency: 'Consistency',
  recovery: 'Recovery',
};

const sportColor = (sport: string): string => {
  const s = sport.toLowerCase();
  if (['running', 'treadmill'].includes(s)) return 'var(--run)';
  if (['walking', 'hiking'].includes(s)) return 'var(--walk)';
  return 'var(--gym)';
};

const tooltipStyle = {
  background: 'var(--bg)', border: '1px solid var(--line-strong)',
  borderRadius: 8, fontSize: 12, color: 'var(--fg)',
};

type Kind = 'month' | 'year';

export const StatsView: React.FC<{
  data: HomeData | null;
  onSelectActivity?: (id: string) => void;
}> = ({ data, onSelectActivity }) => {
  const [kind, setKind] = useState<Kind>('month');
  const [periods, setPeriods] = useState<ReportPeriodOption[]>([]);
  const [selected, setSelected] = useState<string>('');
  const [report, setReport] = useState<PeriodReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Which months and years exist comes from the athlete's own training, so an
  // empty February is never offered.
  useEffect(() => {
    let cancelled = false;
    getReportPeriods(kind)
      .then((list) => {
        if (cancelled) return;
        setPeriods(list);
        setSelected(list[0]?.key ?? '');
      })
      .catch(() => { if (!cancelled) setPeriods([]); });
    return () => { cancelled = true; };
  }, [kind]);

  useEffect(() => {
    if (!selected) { setReport(null); return; }
    let cancelled = false;
    setBusy(true);
    getPeriodReport(kind, selected, 0)
      .then((r) => { if (!cancelled) { setReport(r); setError(null); } })
      .catch((e) => { if (!cancelled) setError(describeError(e, 'Could not load that report')); })
      .finally(() => { if (!cancelled) setBusy(false); });
    return () => { cancelled = true; };
  }, [kind, selected]);

  const radar = useMemo(
    () => Object.entries(data?.attributes ?? {}).map(([k, v]) => ({
      axis: ATTRIBUTE_LABELS[k] ?? k, value: v,
    })),
    [data]
  );

  const donut = useMemo(
    () => Object.entries(data?.split ?? {}).map(([sport, v]) => ({
      name: sport, value: Number(v.hours.toFixed(1)), count: v.count, color: sportColor(sport),
    })),
    [data]
  );

  const savePdf = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      await downloadReportPdf(kind, selected);
      setError(null);
    } catch (e) {
      setError(describeError(e, 'Could not build the PDF'));
    } finally {
      setSaving(false);
    }
  };

  if (!data || data.empty) {
    return (
      <Empty>Nothing recorded yet. Sync some activities and this fills in.</Empty>
    );
  }

  const { totals, form } = data;

  return (
    <>
      <h1 className="text-2xl font-bold tracking-tight text-fg-strong">Stats</h1>
      <p className="mt-0.5 mb-5 text-sm text-muted">
        Everything since you started, and a report on any month or year.
      </p>

      <Card>
        <StatGrid cols={4}>
          <Stat label="Distance" value={totals.km.toFixed(0)} unit="km" sub="all time" />
          <Stat label="Time" value={totals.hours.toFixed(0)} unit="h"
                sub={`${totals.activities} sessions`} />
          <Stat label="Fitness" value={Math.round(form.ctl)} tone="accent" sub="running CTL" />
          {/* An estimate says so. A figure derived from a best effort is
              worth having when no watch reports one, but not worth passing
              off as a measurement. */}
          <Stat label="VO₂ max" value={data.vo2_max ? Math.round(data.vo2_max) : '—'}
                sub={data.vo2_max && data.vo2_max_estimated
                  ? 'estimated from your best effort'
                  : data.resting_hr ? `resting ${data.resting_hr} bpm` : undefined} />
        </StatGrid>
      </Card>

      <div className="grid md:grid-cols-2 gap-4 mt-6">
        <div>
          <h2 className="text-sm font-bold text-fg-strong mb-3 px-1">Profile</h2>
          <Card className="p-4">
            <div className="h-60">
              <ResponsiveContainer width="100%" height="100%">
                <RadarChart data={radar} outerRadius="72%">
                  <PolarGrid stroke="var(--line)" />
                  <PolarAngleAxis dataKey="axis" tick={{ fontSize: 11, fill: 'var(--muted)' }} />
                  <Radar dataKey="value" stroke="var(--accent)" strokeWidth={2}
                         fill="var(--accent)" fillOpacity={0.22} />
                  <Tooltip contentStyle={tooltipStyle}
                           formatter={(v: number) => [`${v} / 100`, '']} />
                </RadarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>

        <div>
          <h2 className="text-sm font-bold text-fg-strong mb-3 px-1">Where the time goes</h2>
          <Card className="p-4">
            <div className="h-60 flex items-center">
              <ResponsiveContainer width="60%" height="100%">
                <PieChart>
                  <Pie data={donut} dataKey="value" innerRadius="58%" outerRadius="88%"
                       paddingAngle={2} stroke="none">
                    {donut.map((d) => <Cell key={d.name} fill={d.color} />)}
                  </Pie>
                  <Tooltip contentStyle={tooltipStyle}
                           formatter={(v: number, n: string) => [`${v} h`, n]} />
                </PieChart>
              </ResponsiveContainer>
              <ul className="flex-1 space-y-2">
                {donut.map((d) => (
                  <li key={d.name} className="flex items-center gap-2 text-xs">
                    <span className="h-2.5 w-2.5 rounded-full shrink-0"
                          style={{ background: d.color }} />
                    <span className="capitalize text-fg flex-1">{d.name}</span>
                    <span className="text-muted tnum">{d.value}h</span>
                  </li>
                ))}
              </ul>
            </div>
          </Card>
        </div>
      </div>

      {/* The report on screen and the report in the PDF are the same report;
          the download is a way to keep it, not a different document. */}
      <div className="mt-8 pt-6 border-t border-line">
        <div className="flex items-end justify-between gap-4 flex-wrap mb-4">
          <div>
            <h2 className="text-lg font-bold tracking-tight text-fg-strong">Reports</h2>
            <p className="mt-0.5 text-[13px] text-muted">
              Any month or year, compared with the one before it.
            </p>
          </div>
          <button onClick={savePdf} disabled={saving || !selected || report?.empty}
                  className="shrink-0 px-3.5 py-2 text-xs font-semibold rounded-lg border border-line
                             text-muted hover:text-fg hover:border-line-strong transition
                             disabled:opacity-40">
            {saving ? 'Building…' : 'Download PDF'}
          </button>
        </div>

        <div className="flex flex-wrap items-center gap-3 mb-5">
          <div className="flex gap-1 p-1 rounded-lg bg-surface border border-line">
            {(['month', 'year'] as Kind[]).map((k) => (
              <button key={k} onClick={() => setKind(k)}
                className={`px-3 py-1.5 rounded-md text-[13px] font-medium capitalize transition ${
                  kind === k ? 'bg-card text-fg-strong shadow-card' : 'text-muted hover:text-fg'}`}>
                {k}
              </button>
            ))}
          </div>

          {periods.length > 0 && (
            <select value={selected} onChange={(e) => setSelected(e.target.value)}
                    className="bg-surface border border-line rounded-lg px-3 py-2 text-[13px]
                               text-fg focus:outline-none focus:border-accent transition">
              {periods.map((p) => (
                <option key={p.key} value={p.key}>
                  {p.label}{p.complete ? '' : ' (still running)'}
                </option>
              ))}
            </select>
          )}
        </div>

        {error && (
          <div className="mb-5 py-3 px-4 text-[13px] text-negative border border-line
                          rounded-lg bg-surface">
            {error}
          </div>
        )}

        {periods.length === 0 ? (
          <Empty>Nothing to report on yet.</Empty>
        ) : busy && !report ? (
          <Empty>Adding up…</Empty>
        ) : report ? (
          <ReportBody report={report} onSelectActivity={onSelectActivity} />
        ) : null}
      </div>
    </>
  );
};

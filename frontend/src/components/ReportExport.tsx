import React, { useEffect, useState } from 'react';
import { ReportPeriodOption } from '../types';
import { getReportPeriods, downloadReportPdf } from '../api/client';
import { describeError } from '../lib/errors';
import { button, input } from './Modal';

/**
 * Printable recaps, on demand.
 *
 * The list of periods comes from the athlete's own training rather than the
 * calendar: offering an empty February is a worse experience than not offering
 * it at all.
 */
export const ReportExport: React.FC = () => {
  const [kind, setKind] = useState<'month' | 'year'>('month');
  const [periods, setPeriods] = useState<ReportPeriodOption[]>([]);
  const [selected, setSelected] = useState<string>('');
  const [withNote, setWithNote] = useState(true);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setNote(null);
    getReportPeriods(kind)
      .then((list) => {
        if (cancelled) return;
        setPeriods(list);
        setSelected(list[0]?.key ?? '');
      })
      .catch(() => { if (!cancelled) setPeriods([]); });
    return () => { cancelled = true; };
  }, [kind]);

  const save = async () => {
    if (!selected) return;
    setBusy(true);
    setNote(null);
    try {
      await downloadReportPdf(kind, selected, withNote);
      setNote('Report downloaded.');
    } catch (e) {
      setNote(describeError(e, 'Could not build the report.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="text-xs text-muted mb-2">Printable reports</div>

      <div className="flex gap-1 p-1 rounded-lg bg-surface border border-line mb-2">
        {(['month', 'year'] as const).map((k) => (
          <button key={k} onClick={() => setKind(k)}
            className={`flex-1 py-1.5 rounded-md text-[13px] font-medium capitalize transition ${
              kind === k ? 'bg-card text-fg-strong shadow-card' : 'text-muted hover:text-fg'}`}>
            {k}
          </button>
        ))}
      </div>

      {periods.length === 0 ? (
        <p className="text-2xs text-faint">
          Nothing to report on yet. Sync some activities first.
        </p>
      ) : (
        <>
          <select value={selected} onChange={(e) => setSelected(e.target.value)}
                  className={`${input} mb-2`}>
            {periods.map((p) => (
              <option key={p.key} value={p.key}>
                {p.label}{p.complete ? '' : ' (still running)'}
              </option>
            ))}
          </select>

          <label className="flex items-center gap-2 mb-2 text-xs text-muted cursor-pointer">
            <input type="checkbox" checked={withNote}
                   onChange={(e) => setWithNote(e.target.checked)}
                   className="accent-accent" />
            Include the coach's written review
          </label>

          <button disabled={busy || !selected} onClick={save}
                  className={`${button} w-full bg-surface border border-line text-fg hover:border-line-strong`}>
            {busy ? 'Building the PDF…' : 'Download PDF'}
          </button>

          <p className="mt-2 text-2xs text-faint">
            Volume, load, every run and how it compares with the period before. With the
            written review it takes a little longer, because the model has to write it.
          </p>
        </>
      )}

      {note && <p className="mt-2 text-xs text-muted">{note}</p>}
    </div>
  );
};

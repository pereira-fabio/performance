import React, { useState } from 'react';
import { Modal, button } from './Modal';
import { recalculateMetrics, exportMyData } from '../api/client';
import { describeError } from '../lib/errors';
import { ThemePref, getTheme, applyTheme } from '../lib/theme';

const OPTIONS: { value: ThemePref; label: string }[] = [
  { value: 'system', label: 'System' },
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
];

export const AppSettingsModal: React.FC<{
  isOpen: boolean; onClose: () => void; onUpdated: () => void; activityCount: number;
}> = ({ isOpen, onClose, onUpdated, activityCount }) => {
  const [theme, setTheme] = useState<ThemePref>(getTheme());
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Settings" subtitle="Appearance and maintenance">
      <div className="space-y-6">
        <div>
          <div className="text-xs text-muted mb-2">Appearance</div>
          <div className="flex gap-1 p-1 rounded-lg bg-surface border border-line">
            {OPTIONS.map((o) => (
              <button key={o.value}
                onClick={() => { setTheme(o.value); applyTheme(o.value); }}
                className={`flex-1 py-1.5 rounded-md text-[13px] font-medium transition ${
                  theme === o.value ? 'bg-card text-fg-strong shadow-card' : 'text-muted hover:text-fg'}`}>
                {o.label}
              </button>
            ))}
          </div>
        </div>

        <div>
          <div className="text-xs text-muted mb-2">Maintenance</div>
          <button
            disabled={busy}
            onClick={async () => {
              setBusy(true); setNote(null);
              try {
                await recalculateMetrics();
                // Thresholds affect new activities and the curve; stored
                // per-activity load is not recomputed here.
                setNote('Fitness chart rebuilt from stored activity load.');
                onUpdated();
              } catch {
                setNote('Rebuild failed.');
              } finally {
                setBusy(false);
              }
            }}
            className={`${button} w-full bg-surface border border-line text-fg hover:border-line-strong`}>
            {busy ? 'Rebuilding…' : 'Rebuild fitness chart'}
          </button>
          {note && <p className="mt-2 text-xs text-muted">{note}</p>}
        </div>

        <div>
          <div className="text-xs text-muted mb-2">Your data</div>
          <div className="flex gap-2">
            <button disabled={busy}
              onClick={async () => {
                setBusy(true); setNote(null);
                try { await exportMyData(true); setNote('Export downloaded.'); }
                catch (e) { setNote(describeError(e, 'Export failed.')); }
                finally { setBusy(false); }
              }}
              className={`${button} flex-1 bg-surface border border-line text-fg hover:border-line-strong`}>
              Export everything
            </button>
            <button disabled={busy}
              onClick={async () => {
                setBusy(true); setNote(null);
                try { await exportMyData(false); setNote('Summary downloaded.'); }
                catch (e) { setNote(describeError(e, 'Export failed.')); }
                finally { setBusy(false); }
              }}
              className={`${button} flex-1 bg-surface border border-line text-fg hover:border-line-strong`}>
              Summary only
            </button>
          </div>
          <p className="mt-2 text-2xs text-faint">
            Your activities and health as JSON. Everything includes GPS and heart-rate
            traces and is much larger; the summary omits them.
          </p>
        </div>

        <div className="pt-4 border-t border-line text-xs text-muted space-y-1">
          <div className="flex justify-between"><span>Activities stored</span>
            <span className="tnum text-fg">{activityCount}</span></div>
          <div className="flex justify-between"><span>Data location</span>
            <span className="text-fg">This server only</span></div>
        </div>
      </div>
    </Modal>
  );
};

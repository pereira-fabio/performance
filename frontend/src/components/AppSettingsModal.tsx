import React, { useState } from 'react';
import { Modal, button, input } from './Modal';
import { recalculateMetrics, exportMyData, deleteAccount } from '../api/client';
import { describeError } from '../lib/errors';
import { ThemePref, getTheme, applyTheme } from '../lib/theme';
import { ConnectionCard } from './ConnectionCard';

const OPTIONS: { value: ThemePref; label: string }[] = [
  { value: 'system', label: 'System' },
  { value: 'light', label: 'Light' },
  { value: 'dark', label: 'Dark' },
];

export const AppSettingsModal: React.FC<{
  isOpen: boolean; onClose: () => void; onUpdated: () => void;
  activityCount: number; onDeleted: () => void; dataSource?: string;
}> = ({ isOpen, onClose, onUpdated, activityCount, onDeleted, dataSource }) => {
  const [theme, setTheme] = useState<ThemePref>(getTheme());
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [password, setPassword] = useState('');
  const [deleteError, setDeleteError] = useState<string | null>(null);

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

        {dataSource !== 'health_connect' && (
          <div>
            <div className="text-xs text-muted mb-2">Automatic sync</div>
            <ConnectionCard onChanged={onUpdated} />
          </div>
        )}

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

        <div className="pt-4 border-t border-line">
          <div className="text-xs text-negative mb-2">Danger zone</div>
          {!confirming ? (
            <button onClick={() => { setConfirming(true); setDeleteError(null); }}
              className={`${button} w-full bg-surface border border-line text-negative hover:border-negative`}>
              Delete my account
            </button>
          ) : (
            <div className="space-y-2">
              <p className="text-xs text-muted">
                This erases your account and all {activityCount} activities permanently.
                Export your data first if you want to keep it. Existing server backups
                still hold this data until they are pruned.
              </p>
              <input type="password" className={input} placeholder="Confirm your password"
                     value={password} onChange={(e) => setPassword(e.target.value)} />
              {deleteError && <p className="text-xs text-negative">{deleteError}</p>}
              <div className="flex gap-2">
                <button onClick={() => { setConfirming(false); setPassword(''); }}
                        className={`${button} flex-1 text-muted hover:text-fg`}>Cancel</button>
                <button disabled={busy || !password}
                  onClick={async () => {
                    setBusy(true); setDeleteError(null);
                    try { await deleteAccount(password); onDeleted(); }
                    catch (e) { setDeleteError(describeError(e, 'Could not delete the account.')); }
                    finally { setBusy(false); }
                  }}
                  className={`${button} flex-1 bg-negative text-white hover:opacity-90`}>
                  {busy ? 'Deleting…' : 'Delete permanently'}
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
};

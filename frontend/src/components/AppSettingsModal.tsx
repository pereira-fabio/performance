import React, { useEffect, useState } from 'react';
import { Modal, button, input } from './Modal';
import {
  recalculateMetrics, exportMyData, deleteAccount, setDataSource,
  getCycleSummary, setCycleTracking,
} from '../api/client';
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
  const [source, setSource] = useState(dataSource ?? 'health_connect');
  const [cycleOn, setCycleOn] = useState<boolean | null>(null);

  // Read when the panel opens rather than held in the session, so the switch
  // always shows what the server actually has.
  useEffect(() => {
    if (!isOpen) return;
    getCycleSummary().then((c) => setCycleOn(c.enabled)).catch(() => setCycleOn(null));
  }, [isOpen]);

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
          <div className="text-xs text-muted mb-2">Where your training comes from</div>
          {/* Always offered, and always changeable: the choice was previously
              made once at sign-up and then had nowhere to be revisited, which
              left anyone who picked wrongly with no way back. */}
          <div className="flex gap-1 p-1 rounded-lg bg-surface border border-line">
            {[
              { id: 'health_connect', label: 'Android' },
              { id: 'file_import', label: 'Garmin / iPhone' },
            ].map((o) => (
              <button key={o.id}
                onClick={async () => {
                  setSource(o.id);
                  try { await setDataSource(o.id); onUpdated(); }
                  catch { /* the selection still stands for this session */ }
                }}
                className={`flex-1 py-1.5 rounded-md text-[13px] font-medium transition ${
                  source === o.id ? 'bg-card text-fg-strong shadow-card' : 'text-muted hover:text-fg'}`}>
                {o.label}
              </button>
            ))}
          </div>
          <p className="mt-1.5 text-2xs text-faint">
            {source === 'health_connect'
              ? 'The companion app reads Health Connect on your phone.'
              : 'Link Garmin below for automatic sync, or import exported files from the menu.'}
          </p>
        </div>

        {source !== 'health_connect' && (
          <div>
            <div className="text-xs text-muted mb-2">Automatic sync</div>
            <ConnectionCard onChanged={onUpdated} />
          </div>
        )}

        {cycleOn !== null && (
          <div>
            <div className="text-xs text-muted mb-2">Cycle tracking</div>
            <label className="flex items-start gap-3 cursor-pointer">
              <input type="checkbox" checked={cycleOn} className="mt-0.5 accent-accent"
                     onChange={async (e) => {
                       const next = e.target.checked;
                       setCycleOn(next);
                       try {
                         await setCycleTracking(next);
                         onUpdated();
                       } catch {
                         setCycleOn(!next);
                         setNote('Could not change that setting.');
                       }
                     }} />
              <span className="text-[13px] text-fg">
                Track your menstrual cycle
                <span className="block text-2xs text-faint mt-0.5">
                  Adds a cycle section to your home page and a calendar to log period days,
                  with the next one predicted from the ones before it. Switching this off
                  hides it and keeps what you logged; it never leaves this server, and it is
                  never sent to the coach.
                </span>
              </span>
            </label>
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

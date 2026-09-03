import React, { useState, useEffect } from 'react';
import { UserProfile } from '../types';
import { getUserProfile, updateUserProfile, recalculateMetrics } from '../api/client';
import { Modal, Field, input, button } from './Modal';

export const SettingsModal: React.FC<{ isOpen: boolean; onClose: () => void; onUpdated: () => void }> = ({
  isOpen, onClose, onUpdated,
}) => {
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [saving, setSaving] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  useEffect(() => { if (isOpen) getUserProfile().then(setProfile).catch(() => setNote('Could not load profile')); }, [isOpen]);
  if (!isOpen) return null;

  const paceText = (sec: number) => `${Math.floor(sec / 60)}:${Math.round(sec % 60).toString().padStart(2, '0')}`;
  const paceSec = (t: string) => {
    const [m, s] = t.split(':').map(Number);
    return isFinite(m) && isFinite(s) ? m * 60 + s : profile?.threshold_pace_sec ?? 240;
  };

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profile) return;
    setSaving(true);
    try {
      await updateUserProfile(profile);
      onUpdated();
      onClose();
    } catch {
      setNote('Save failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Athlete profile"
           subtitle="Used for heart-rate zones, training load and threshold pace">
      {!profile ? (
        <p className="text-[13px] text-muted">Loading…</p>
      ) : (
        <form onSubmit={save} className="space-y-4">
          <Field label="Name">
            <input className={input} value={profile.name}
                   onChange={(e) => setProfile({ ...profile, name: e.target.value })} />
          </Field>

          <div className="grid grid-cols-3 gap-3">
            <Field label="Max HR">
              <input type="number" className={input} value={profile.max_hr}
                     onChange={(e) => setProfile({ ...profile, max_hr: +e.target.value })} />
            </Field>
            <Field label="Resting HR">
              <input type="number" className={input} value={profile.resting_hr}
                     onChange={(e) => setProfile({ ...profile, resting_hr: +e.target.value })} />
            </Field>
            <Field label="Threshold HR">
              <input type="number" className={input} value={profile.lthr}
                     onChange={(e) => setProfile({ ...profile, lthr: +e.target.value })} />
            </Field>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <Field label="Threshold pace" hint="min:sec per km">
              <input className={input} defaultValue={paceText(profile.threshold_pace_sec)}
                     onBlur={(e) => setProfile({ ...profile, threshold_pace_sec: paceSec(e.target.value) })} />
            </Field>
            <Field label="Weight" hint="kg">
              <input type="number" className={input} value={profile.weight_kg}
                     onChange={(e) => setProfile({ ...profile, weight_kg: +e.target.value })} />
            </Field>
          </div>

          {note && <p className="text-2xs text-negative">{note}</p>}

          <div className="flex items-center justify-between pt-1">
            <button type="button"
              onClick={async () => {
                setNote(null);
                try {
                  await recalculateMetrics();
                  // Thresholds apply to new activities and to the fitness curve;
                  // stored per-activity load is not recomputed.
                  setNote('Fitness chart rebuilt. Stored per-activity load is unchanged.');
                  onUpdated();
                } catch { setNote('Rebuild failed'); }
              }}
              className={`${button} text-muted hover:text-fg`}>
              Rebuild chart
            </button>
            <div className="flex gap-2">
              <button type="button" onClick={onClose} className={`${button} text-muted hover:text-fg`}>Cancel</button>
              <button type="submit" disabled={saving}
                      className={`${button} bg-accent text-white hover:opacity-90`}>
                {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          </div>
        </form>
      )}
    </Modal>
  );
};

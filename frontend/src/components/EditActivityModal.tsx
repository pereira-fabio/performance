import React, { useEffect, useState } from 'react';
import { Activity } from '../types';
import { Modal, Field, input, button } from './Modal';
import { editActivity, getWorkoutTags } from '../api/client';
import { describeError } from '../lib/errors';

/**
 * Correct or annotate one activity.
 *
 * Deliberately not the measurements. Distance, duration and heart rate are what
 * pace, load, zones, records and the fitness curve are all computed from, and
 * changing one here without replaying the session through the physiology engine
 * would leave an activity whose own figures disagree. A wrong distance is a
 * re-sync, not a correction.
 *
 * What is editable is either descriptive, or a value the device simply never
 * wrote and nothing derives anything from.
 */

const SPORTS: { value: string; label: string }[] = [
  { value: 'running', label: 'Run' },
  { value: 'treadmill', label: 'Treadmill run' },
  { value: 'walking', label: 'Walk' },
  { value: 'hiking', label: 'Hike' },
  { value: 'cycling', label: 'Ride' },
  { value: 'swimming', label: 'Swim' },
  { value: 'rowing', label: 'Row' },
  { value: 'gym', label: 'Gym session' },
  { value: 'other', label: 'Other' },
];

const TAG_LABELS: Record<string, string> = {
  recovery: 'Recovery',
  easy: 'Easy',
  long: 'Long',
  tempo: 'Tempo',
  interval: 'Intervals',
  race: 'Race',
};

export const EditActivityModal: React.FC<{
  activity: Activity | null;
  onClose: () => void;
  onSaved: (updated: Activity) => void;
  onDelete: (id: string) => void;
}> = ({ activity, onClose, onSaved, onDelete }) => {
  const [name, setName] = useState('');
  const [sport, setSport] = useState('running');
  const [tag, setTag] = useState<string | null>(null);
  const [calories, setCalories] = useState<string>('');
  const [steps, setSteps] = useState<string>('');
  const [notes, setNotes] = useState('');
  const [tags, setTags] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Reset from the activity every time one is opened, so the form never shows
  // the previous activity's values for a moment.
  useEffect(() => {
    if (!activity) return;
    setName(activity.name ?? '');
    setSport((activity.sport_type ?? 'running').toLowerCase());
    setTag(activity.workout_tag ?? null);
    setCalories(activity.calories_kcal != null ? String(Math.round(activity.calories_kcal)) : '');
    setSteps(activity.steps != null ? String(activity.steps) : '');
    setNotes(activity.notes ?? '');
    setConfirming(false);
    setError(null);
  }, [activity?.id]);

  useEffect(() => { getWorkoutTags().then(setTags).catch(() => setTags([])); }, []);

  if (!activity) return null;

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const updated = await editActivity(activity.id, {
        name: name.trim(),
        sport_type: sport,
        workout_tag: tag,
        notes: notes.trim() || null,
        // An empty box means "still not recorded", not zero.
        calories_kcal: calories === '' ? null : Number(calories),
        steps: steps === '' ? null : Number(steps),
      });
      onSaved(updated);
      onClose();
    } catch (err) {
      setError(describeError(err, 'Could not save those changes'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal isOpen={Boolean(activity)} onClose={onClose} title="Edit activity"
           subtitle="What it was, and anything the device did not record">
      <form onSubmit={save} className="space-y-4">
        <Field label="Name">
          <input className={input} value={name} onChange={(e) => setName(e.target.value)} />
        </Field>

        <Field label="Sport" hint="Moves it to the matching tab">
          <select className={input} value={sport} onChange={(e) => setSport(e.target.value)}>
            {SPORTS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
          </select>
        </Field>

        <div>
          <span className="text-2xs text-muted">Type of session</span>
          <div className="mt-1.5 flex flex-wrap gap-1.5">
            {tags.map((t) => (
              <button key={t} type="button"
                      onClick={() => setTag(tag === t ? null : t)}
                      className={`px-2.5 py-1 rounded-lg text-2xs font-semibold transition ${
                        tag === t
                          ? 'bg-accent text-white'
                          : 'bg-surface border border-line text-muted hover:text-fg'}`}>
                {TAG_LABELS[t] ?? t}
              </button>
            ))}
          </div>
          <p className="mt-1.5 text-2xs text-faint">
            Tap again to clear. The watch records what happened; only you know whether an
            easy pace was a recovery jog or all you had left.
          </p>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Field label="Calories" hint="kcal">
            <input type="number" min="0" max="30000" className={input} value={calories}
                   placeholder="not recorded"
                   onChange={(e) => setCalories(e.target.value)} />
          </Field>
          <Field label="Steps">
            <input type="number" min="0" max="500000" className={input} value={steps}
                   placeholder="not recorded"
                   onChange={(e) => setSteps(e.target.value)} />
          </Field>
        </div>

        <Field label="Notes">
          <textarea className={`${input} min-h-[4.5rem]`} value={notes}
                    placeholder="How it felt, the weather, anything the numbers miss"
                    onChange={(e) => setNotes(e.target.value)} />
        </Field>

        <p className="text-2xs text-faint">
          Distance, duration and heart rate are not editable here. Everything else — pace,
          training load, zones, records — is computed from them, and changing one on its own
          would leave this activity's figures disagreeing with each other. If those are
          wrong, re-sync the activity.
        </p>

        {error && <p className="text-2xs text-negative">{error}</p>}

        <div className="flex items-center justify-end gap-2 pt-1">
          <button type="button" onClick={onClose}
                  className={`${button} text-muted hover:text-fg`}>Cancel</button>
          <button type="submit" disabled={saving || !name.trim()}
                  className={`${button} bg-accent text-white hover:opacity-90`}>
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>

        {/* Below the buttons and behind a confirmation: deleting an activity
            removes its GPS trace and everything derived from it, and a re-sync
            only brings it back if the source still has it. */}
        <div className="mt-6 pt-4 border-t border-line">
          {!confirming ? (
            <button type="button" onClick={() => setConfirming(true)}
                    className="text-xs text-faint hover:text-negative transition">
              Delete this activity
            </button>
          ) : (
            <div className="space-y-2">
              <p className="text-2xs text-muted">
                This removes the activity and its GPS and heart-rate traces. A re-sync brings
                it back only if the phone or watch still has it.
              </p>
              <div className="flex gap-2">
                <button type="button" onClick={() => setConfirming(false)}
                        className={`${button} flex-1 text-muted hover:text-fg`}>Keep it</button>
                <button type="button" onClick={() => onDelete(activity.id)}
                        className={`${button} flex-1 bg-negative text-white hover:opacity-90`}>
                  Delete
                </button>
              </div>
            </div>
          )}
        </div>
      </form>
    </Modal>
  );
};

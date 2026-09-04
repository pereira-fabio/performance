import React, { useEffect, useState } from 'react';
import { CoachNote as Note, getActivityNote, getWeeklyNote } from '../api/client';
import { Card } from './Stat';

/**
 * Written commentary from the local model.
 *
 * Presented deliberately unlike the metrics around it: the rest of this app
 * distinguishes measurements from estimates, and generated prose is a third
 * thing again. It says which model wrote it, and it never appears where a
 * figure should be.
 */
export const CoachNoteCard: React.FC<{ activityId?: string; title?: string }> = ({
  activityId, title = 'Coach',
}) => {
  const [note, setNote] = useState<Note | null>(null);
  const [busy, setBusy] = useState(true);

  const load = async (refresh = false) => {
    setBusy(true);
    try {
      setNote(activityId ? await getActivityNote(activityId, refresh) : await getWeeklyNote(refresh));
    } catch {
      setNote({ available: false, reason: 'The coach could not be reached.' });
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [activityId]);

  // Nothing configured, or nothing to say: stay out of the way entirely.
  if (!busy && (!note || !note.available)) return null;

  return (
    <section className="mt-6">
      <div className="flex items-baseline justify-between mb-3 px-1">
        <h2 className="text-sm font-bold text-fg-strong tracking-tight">{title}</h2>
        {note?.available && (
          <button onClick={() => load(true)} disabled={busy}
                  className="text-2xs text-faint hover:text-muted transition disabled:opacity-50">
            {busy ? 'Writing…' : 'Rewrite'}
          </button>
        )}
      </div>
      <Card className="p-5">
        {busy && !note?.text ? (
          <p className="text-[13px] text-muted">Reading your training…</p>
        ) : (
          <>
            <p className="text-[13px] leading-relaxed text-fg whitespace-pre-line">{note?.text}</p>
            <p className="mt-3 pt-3 border-t border-line text-2xs text-faint">
              Written by {note?.model ?? 'a language model'} running on your own server, from the
              figures above. It phrases them; it does not measure anything.
            </p>
          </>
        )}
      </Card>
    </section>
  );
};

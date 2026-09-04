import React, { useState } from 'react';
import { button } from './Modal';
import { importFiles } from '../api/client';
import { describeError } from '../lib/errors';

/**
 * Bring activities in from files.
 *
 * A panel rather than a screen of its own: importing is something you do to
 * set an account up or to backfill a gap, which is the same errand as the rest
 * of settings, and it did not earn a place in the main menu beside the things
 * you open every day.
 */
export const ImportPanel: React.FC<{
  onImported: () => void;
  dataSource?: string;
}> = ({ onImported, dataSource }) => {
  const [files, setFiles] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [problems, setProblems] = useState<string[]>([]);

  const run = async () => {
    if (!files.length) return;
    setBusy(true); setResult(null); setProblems([]);
    try {
      const r = await importFiles(files);
      setResult(
        `Imported ${r.imported} activit${r.imported === 1 ? 'y' : 'ies'}` +
        (r.skipped ? `, skipped ${r.skipped}` : '') + '.'
      );
      setProblems(r.problems);
      setFiles([]);
      onImported();
    } catch (e) {
      setResult(describeError(e, 'Import failed.'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div>
      <div className="text-xs text-muted mb-2">Import activities</div>

      {dataSource === 'file_import' && (
        <div className="mb-2 p-3 rounded-lg bg-accent-soft border border-line text-2xs text-muted">
          <p className="font-semibold text-fg-strong text-xs mb-1">From Garmin Connect</p>
          <p>One activity: open it, then the ⚙ menu → Export to TCX or GPX.</p>
          <p className="mt-1">
            Everything: Account settings → Data Management → Export All Data. Upload the
            zip as it downloads — it holds FIT files and can be imported whole.
          </p>
        </div>
      )}

      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); setFiles(Array.from(e.dataTransfer.files)); }}
        onClick={() => document.getElementById('import-input')?.click()}
        className="border border-dashed border-line-strong rounded-lg py-7 text-center
                   cursor-pointer hover:border-accent transition"
      >
        <input id="import-input" type="file" multiple accept=".gpx,.tcx,.fit,.zip"
               className="hidden"
               onChange={(e) => setFiles(Array.from(e.target.files ?? []))} />
        {files.length ? (
          <>
            <p className="text-[13px] text-fg-strong">
              {files.length === 1 ? files[0].name : `${files.length} files`}
            </p>
            <p className="text-2xs text-muted mt-0.5 tnum">
              {(files.reduce((s, f) => s + f.size, 0) / 1048576).toFixed(1)} MB
            </p>
          </>
        ) : (
          <>
            <p className="text-[13px] text-muted">Drop files here</p>
            <p className="text-2xs text-faint mt-0.5">GPX · TCX · FIT · ZIP</p>
          </>
        )}
      </div>

      {files.length > 0 && (
        <button onClick={run} disabled={busy}
                className={`${button} w-full mt-2 bg-accent text-white hover:opacity-90`}>
          {busy ? 'Importing…' : `Import ${files.length} file${files.length === 1 ? '' : 's'}`}
        </button>
      )}

      {result && <p className="mt-2 text-[13px] text-fg">{result}</p>}
      {problems.length > 0 && (
        <details className="mt-1">
          <summary className="text-2xs text-muted cursor-pointer">
            {problems.length} file{problems.length === 1 ? '' : 's'} could not be read
          </summary>
          <ul className="mt-1 space-y-0.5 max-h-32 overflow-y-auto">
            {problems.map((p, i) => <li key={i} className="text-2xs text-faint">{p}</li>)}
          </ul>
        </details>
      )}
    </div>
  );
};

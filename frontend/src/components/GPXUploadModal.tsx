import React, { useState } from 'react';
import { uploadGPX } from '../api/client';
import { Activity } from '../types';
import { Modal, input, button } from './Modal';
import { describeError } from '../lib/errors';

export const GPXUploadModal: React.FC<{
  isOpen: boolean; onClose: () => void; onUploaded: (a: Activity) => void;
}> = ({ isOpen, onClose, onUploaded }) => {
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const upload = async () => {
    if (!file) return;
    setBusy(true); setError(null);
    try {
      onUploaded(await uploadGPX(file));
      setFile(null);
      onClose();
    } catch (err: any) {
      setError(describeError(err, 'Could not read that file'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="Import a GPX file"
           subtitle="For activities that never reached Health Connect">
      <div
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => { e.preventDefault(); if (e.dataTransfer.files[0]) setFile(e.dataTransfer.files[0]); }}
        onClick={() => document.getElementById('gpx-input')?.click()}
        className="border border-dashed border-line-strong rounded-lg py-10 text-center cursor-pointer hover:border-accent transition"
      >
        <input id="gpx-input" type="file" accept=".gpx" className="hidden"
               onChange={(e) => e.target.files?.[0] && setFile(e.target.files[0])} />
        {file ? (
          <>
            <p className="text-[13px] text-fg-strong">{file.name}</p>
            <p className="text-2xs text-muted mt-0.5 tnum">{(file.size / 1024).toFixed(0)} KB</p>
          </>
        ) : (
          <>
            <p className="text-[13px] text-muted">Drop a .gpx file here</p>
            <p className="text-2xs text-faint mt-0.5">or click to choose</p>
          </>
        )}
      </div>

      {error && <p className="mt-3 text-2xs text-negative">{error}</p>}

      <div className="flex justify-end gap-2 mt-5">
        <button onClick={onClose} className={`${button} text-muted hover:text-fg`}>Cancel</button>
        <button onClick={upload} disabled={!file || busy}
                className={`${button} bg-accent text-white hover:opacity-90`}>
          {busy ? 'Analysing…' : 'Import'}
        </button>
      </div>
    </Modal>
  );
};

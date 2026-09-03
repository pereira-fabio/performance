import React, { useState } from 'react';
import { uploadGPX } from '../api/client';
import { X, Upload, CheckCircle2, AlertCircle, FileText } from 'lucide-react';
import { Activity } from '../types';

interface GPXUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploaded: (activity: Activity) => void;
}

export const GPXUploadModal: React.FC<GPXUploadModalProps> = ({ isOpen, onClose, onUploaded }) => {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      setFile(e.dataTransfer.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const act = await uploadGPX(file);
      onUploaded(act);
      onClose();
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to parse GPX file');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm">
      <div className="bg-gray-900 border border-gray-800 rounded-2xl w-full max-w-md overflow-hidden shadow-2xl">
        <div className="p-5 border-b border-gray-800 flex items-center justify-between">
          <div className="flex items-center space-x-2.5">
            <div className="p-2 rounded-xl bg-cyan-500/10 text-cyan-400">
              <Upload className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white">Import GPX / Workout File</h2>
              <p className="text-xs text-gray-400">Upload standalone running files</p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white p-1 rounded-lg">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          <div
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleDrop}
            className="border-2 border-dashed border-gray-700 hover:border-cyan-500/60 rounded-2xl p-8 text-center bg-gray-950/40 cursor-pointer transition"
            onClick={() => document.getElementById('gpx-file-input')?.click()}
          >
            <input
              id="gpx-file-input"
              type="file"
              accept=".gpx"
              className="hidden"
              onChange={(e) => {
                if (e.target.files && e.target.files.length > 0) {
                  setFile(e.target.files[0]);
                }
              }}
            />
            {file ? (
              <div className="flex flex-col items-center">
                <FileText className="w-10 h-10 text-cyan-400 mb-2" />
                <span className="text-sm font-bold text-white">{file.name}</span>
                <span className="text-xs text-gray-400 mt-1">{(file.size / 1024).toFixed(1)} KB</span>
              </div>
            ) : (
              <div className="flex flex-col items-center">
                <Upload className="w-10 h-10 text-gray-600 mb-2" />
                <span className="text-xs font-semibold text-gray-300">Drag & drop your .gpx file here</span>
                <span className="text-[11px] text-gray-500 mt-1">or click to browse local files</span>
              </div>
            )}
          </div>

          {error && (
            <div className="p-3 bg-rose-950/50 border border-rose-800 rounded-xl text-xs text-rose-300 flex items-center space-x-2">
              <AlertCircle className="w-4 h-4 text-rose-400 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="flex items-center justify-end space-x-2 pt-2">
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-xl text-gray-400 hover:text-white bg-gray-800 font-semibold text-xs transition"
            >
              Cancel
            </button>
            <button
              onClick={handleUpload}
              disabled={!file || uploading}
              className="flex items-center space-x-1.5 px-4 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 disabled:opacity-50 text-white font-bold text-xs shadow-lg shadow-cyan-500/20 transition"
            >
              <span>{uploading ? 'Analyzing...' : 'Upload & Analyze'}</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

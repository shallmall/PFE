import React, { useState, useRef } from 'react';
import { Upload, X, FileJson, AlertCircle, CheckCircle, Loader2, ShieldAlert, ArrowRight } from 'lucide-react';

export default function SubmissionModal({ isOpen, onClose, onSuccess }) {
  const [dragActive, setDragActive] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileContent, setFileContent] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

  if (!isOpen) return null;

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleChange = (e) => {
    e.preventDefault();
    if (e.target.files && e.target.files[0]) {
      processFile(e.target.files[0]);
    }
  };

  const processFile = (file) => {
    setError(null);
    if (!file.name.endsWith('.json')) {
      setError("Please select a valid .json batch submission file.");
      return;
    }
    setSelectedFile(file);
    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const json = JSON.parse(event.target.result);
        if (!json.submitter_id || !json.reviews || !Array.isArray(json.reviews)) {
          setError("Invalid JSON format. Must contain 'submitter_id' and 'reviews' array.");
          return;
        }
        setFileContent(json);
      } catch (err) {
        setError("Failed to parse JSON file. Ensure it is valid JSON.");
      }
    };
    reader.readAsText(file);
  };

  const handleSubmit = async () => {
    if (!fileContent) return;
    setLoading(true);
    setError(null);

    try {
      const res = await fetch('/api/v1/reviews/batch_submit', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(fileContent)
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({ detail: "Network error occurred" }));
        if (res.status === 401 || res.status === 403 || (errData.detail && errData.detail.toLowerCase().includes("auth"))) {
          throw new Error("Submission Refused: Submitter ID not registered or API Key encryption hash mismatch.");
        }
        throw new Error(errData.detail || `Submission failed with HTTP status ${res.status}`);
      }

      const data = await res.json();
      onSuccess(data);
      onClose();
    } catch (err) {
      console.error("Submission Error:", err);
      setError(err.message || "Failed to submit review batch to AI Engine.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fadeIn">
      <div className="glass-modal w-full max-w-2xl rounded-3xl p-8 relative overflow-hidden shadow-2xl border border-slate-700">
        
        {/* Background Glow */}
        <div className="absolute -top-24 -right-24 w-48 h-48 bg-emerald-500/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute -bottom-24 -left-24 w-48 h-48 bg-cyan-500/10 rounded-full blur-3xl pointer-events-none" />

        {/* Close Button */}
        <button 
          onClick={onClose}
          className="absolute top-6 right-6 text-slate-400 hover:text-white bg-slate-800/80 hover:bg-slate-700 p-2 rounded-full transition-all"
        >
          <X className="w-5 h-5" />
        </button>

        {/* Header */}
        <div className="mb-6">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-xs font-semibold uppercase tracking-wider mb-3">
            <Upload className="w-3.5 h-3.5" />
            <span>Enterprise Submitter Portal</span>
          </div>
          <h2 className="text-2xl font-bold text-white tracking-tight">
            Upload Review Batch JSON
          </h2>
          <p className="text-sm text-slate-400 mt-1">
            Drag and drop your enterprise review batch payload. Our backend will automatically verify your registered Submitter ID and cryptographic API key hash before processing through the Late Fusion AI Engine.
          </p>
        </div>

        {/* Rejection / Error Banner */}
        {error && (
          <div className="mb-6 p-4 rounded-2xl bg-rose-500/10 border border-rose-500/40 flex items-start gap-3 text-rose-300 animate-shake">
            <ShieldAlert className="w-6 h-6 text-rose-400 flex-shrink-0 mt-0.5" />
            <div>
              <h4 className="text-sm font-bold text-rose-200">Security / Verification Refusal</h4>
              <p className="text-xs mt-1 leading-relaxed text-rose-300/90">{error}</p>
            </div>
          </div>
        )}

        {/* Drag and Drop Zone */}
        {!selectedFile ? (
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`border-2 border-dashed rounded-3xl p-10 text-center cursor-pointer transition-all flex flex-col items-center justify-center gap-4 ${
              dragActive 
                ? 'border-emerald-400 bg-emerald-500/10 scale-[1.01]' 
                : 'border-slate-700 hover:border-slate-500 bg-slate-900/40 hover:bg-slate-900/60'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".json"
              onChange={handleChange}
              className="hidden"
            />
            <div className="w-16 h-16 rounded-2xl bg-slate-800/80 flex items-center justify-center text-emerald-400 shadow-inner">
              <FileJson className="w-8 h-8" />
            </div>
            <div>
              <p className="text-base font-semibold text-slate-200">
                Click to upload or drag and drop
              </p>
              <p className="text-xs text-slate-400 mt-1">
                Must be a valid JSON payload (e.g. amazon_50_products_all_reviews.json)
              </p>
            </div>
          </div>
        ) : (
          /* File Selected Summary Card */
          <div className="bg-slate-900/80 border border-slate-700/80 rounded-3xl p-6 mb-6">
            <div className="flex items-center justify-between mb-4 pb-4 border-b border-slate-800">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-xl bg-emerald-500/20 text-emerald-400 flex items-center justify-center font-bold">
                  JSON
                </div>
                <div>
                  <h4 className="text-sm font-bold text-white truncate max-w-md">{selectedFile.name}</h4>
                  <p className="text-xs text-slate-400">{(selectedFile.size / 1024).toFixed(2)} KB • Ready for AI Pipeline</p>
                </div>
              </div>
              <button 
                onClick={() => { setSelectedFile(null); setFileContent(null); setError(null); }}
                className="text-xs text-slate-400 hover:text-rose-400 underline"
              >
                Change File
              </button>
            </div>

            {fileContent && (
              <div className="grid grid-cols-2 gap-3 bg-slate-950/60 p-4 rounded-2xl text-xs">
                <div>
                  <span className="text-slate-400 block mb-1">Detected Submitter ID:</span>
                  <span className="font-mono font-bold text-cyan-400 bg-cyan-950/40 px-2 py-1 rounded border border-cyan-800/50 inline-block">
                    {fileContent.submitter_id}
                  </span>
                </div>
                <div>
                  <span className="text-slate-400 block mb-1">Total Reviews in Batch:</span>
                  <span className="font-mono font-bold text-emerald-400 bg-emerald-950/40 px-2 py-1 rounded border border-emerald-800/50 inline-block">
                    {fileContent.reviews?.length || 0} reviews
                  </span>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Footer Actions */}
        <div className="flex items-center justify-end gap-3 mt-8">
          <button
            onClick={onClose}
            disabled={loading}
            className="px-5 py-2.5 rounded-xl text-sm font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition-all"
          >
            Cancel
          </button>
          <button
            onClick={handleSubmit}
            disabled={!fileContent || loading}
            className="flex items-center gap-2 px-6 py-2.5 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 disabled:opacity-40 text-white font-medium text-sm rounded-xl shadow-lg shadow-emerald-500/20 transition-all hover:scale-105 active:scale-95"
          >
            {loading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Running AI Late Fusion & Web3 Sync...</span>
              </>
            ) : (
              <>
                <span>Verify & Process Batch</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </div>

      </div>
    </div>
  );
}

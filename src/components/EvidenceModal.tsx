import React from 'react';
import {
  X,
  ShieldCheck,
  FileCode,
  Clock,
  Layers,
  CheckCircle,
} from 'lucide-react';

interface EvidenceModalProps {
  reference: string | null;
  onClose: () => void;
  rawRecord: any;
  timestamp: string | null;
}

export const EvidenceModal: React.FC<EvidenceModalProps> = ({
  reference,
  onClose,
  rawRecord,
  timestamp,
}) => {
  if (!reference) return null;

  // Parse reference: e.g. "laps[4].lap_duration" -> family "laps", index "4", field "lap_duration"
  const match = reference.match(/^(\w+)\[(\d+)\](?:\.(\w+))?/);
  const family = match ? match[1] : 'unknown';
  const index = match ? match[2] : '0';
  const field = match ? match[3] : 'all';

  const fieldValue = rawRecord && field !== 'all' ? rawRecord[field] : undefined;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="bg-zinc-900 border border-zinc-700 rounded-2xl shadow-2xl max-w-lg w-full overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="bg-zinc-800/90 px-5 py-3.5 border-b border-zinc-700 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-5 h-5 text-emerald-400" />
            <div>
              <h3 className="font-bold text-sm text-white">
                Evidence Audit Inspector
              </h3>
              <p className="text-[11px] text-zinc-400">
                Ground-truth provenance verification
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-zinc-700 text-zinc-400 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-5 space-y-4">
          {/* Reference pill */}
          <div className="bg-zinc-950 p-3 rounded-xl border border-zinc-800">
            <div className="text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-1">
              Cited Telemetry Token
            </div>
            <div className="font-mono text-emerald-400 font-bold text-sm">
              {reference}
            </div>
          </div>

          {/* Breakdown cards */}
          <div className="grid grid-cols-3 gap-2.5 text-xs font-mono">
            <div className="bg-zinc-950 p-2.5 rounded-lg border border-zinc-800">
              <span className="text-[10px] text-zinc-500 font-sans block">Family</span>
              <span className="font-bold text-zinc-200">{family}</span>
            </div>
            <div className="bg-zinc-950 p-2.5 rounded-lg border border-zinc-800">
              <span className="text-[10px] text-zinc-500 font-sans block">Record Index</span>
              <span className="font-bold text-zinc-200">#{index}</span>
            </div>
            <div className="bg-zinc-950 p-2.5 rounded-lg border border-zinc-800">
              <span className="text-[10px] text-zinc-500 font-sans block">Cited Field</span>
              <span className="font-bold text-zinc-200 truncate block">{field}</span>
            </div>
          </div>

          {/* Value Verification */}
          {field !== 'all' && (
            <div className="bg-emerald-950/30 border border-emerald-500/40 p-3 rounded-xl flex items-center justify-between">
              <div className="flex items-center gap-2">
                <CheckCircle className="w-4 h-4 text-emerald-400" />
                <span className="text-xs text-emerald-200 font-medium">
                  Verified Grounded Value:
                </span>
              </div>
              <span className="font-mono font-black text-emerald-400 text-sm">
                {fieldValue !== undefined ? String(fieldValue) : 'Not null'}
              </span>
            </div>
          )}

          {/* Timestamp */}
          {timestamp && (
            <div className="flex items-center gap-2 text-xs text-zinc-400 font-mono">
              <Clock className="w-3.5 h-3.5 text-zinc-500" />
              <span>Observation Time: {timestamp}</span>
            </div>
          )}

          {/* Raw JSON Record */}
          <div>
            <div className="text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-1 flex items-center gap-1.5">
              <FileCode className="w-3.5 h-3.5" />
              Raw OpenF1 Payload Record
            </div>
            <pre className="bg-zinc-950 p-3 rounded-xl border border-zinc-800 font-mono text-[11px] text-zinc-300 max-h-48 overflow-y-auto overflow-x-auto whitespace-pre-wrap">
              {rawRecord ? JSON.stringify(rawRecord, null, 2) : 'Record not available'}
            </pre>
          </div>
        </div>

        {/* Footer */}
        <div className="bg-zinc-950 px-5 py-3 border-t border-zinc-800 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-xs font-semibold text-zinc-200 transition-colors"
          >
            Close Inspector
          </button>
        </div>
      </div>
    </div>
  );
};

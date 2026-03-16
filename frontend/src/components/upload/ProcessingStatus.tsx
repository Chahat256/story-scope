import { Loader2, CheckCircle } from "lucide-react";
import type { JobStatusResponse } from "@/types/analysis";

interface Props {
  status: JobStatusResponse;
}

const STAGES = [
  { key: "extracting", label: "Extracting text" },
  { key: "chunking", label: "Processing pages" },
  { key: "indexing", label: "Building index" },
  { key: "analyzing", label: "Literary analysis" },
];

export default function ProcessingStatus({ status }: Props) {
  const currentStageIdx = STAGES.findIndex((s) => s.key === status.status);

  return (
    <div className="max-w-2xl mx-auto px-6 pt-20 text-center">
      <div className="bg-white border border-ink-200 rounded-2xl p-10">
        <div className="flex justify-center mb-6">
          <Loader2 className="w-12 h-12 text-ink-600 animate-spin" />
        </div>
        <h2 className="font-serif text-2xl text-ink-900 mb-2">
          Analyzing your novel...
        </h2>
        <p className="text-ink-500 mb-8 text-sm">{status.message}</p>

        {/* Progress bar */}
        <div className="w-full bg-ink-100 rounded-full h-2 mb-8">
          <div
            className="bg-ink-700 h-2 rounded-full transition-all duration-500"
            style={{ width: `${status.progress}%` }}
          />
        </div>

        {/* Stage indicators */}
        <div className="grid grid-cols-4 gap-2">
          {STAGES.map((stage, i) => {
            const isDone = currentStageIdx > i || status.status === "complete";
            const isCurrent = currentStageIdx === i;
            return (
              <div key={stage.key} className="text-center">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center mx-auto mb-1.5 text-xs ${
                    isDone
                      ? "bg-emerald-100 text-emerald-700"
                      : isCurrent
                      ? "bg-ink-100 text-ink-700"
                      : "bg-ink-50 text-ink-300"
                  }`}
                >
                  {isDone ? <CheckCircle className="w-4 h-4" /> : i + 1}
                </div>
                <span
                  className={`text-xs ${
                    isCurrent ? "text-ink-700 font-medium" : isDone ? "text-emerald-600" : "text-ink-300"
                  }`}
                >
                  {stage.label}
                </span>
              </div>
            );
          })}
        </div>

        <p className="text-xs text-ink-400 mt-8">
          Literary analysis takes 1–3 minutes depending on novel length.
          <br />
          This page will update automatically.
        </p>
      </div>
    </div>
  );
}

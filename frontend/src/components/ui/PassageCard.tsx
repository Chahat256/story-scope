import { Quote } from "lucide-react";
import type { SupportingPassage } from "@/types/analysis";

interface Props {
  passage: SupportingPassage;
  index?: number;
}

export default function PassageCard({ passage, index }: Props) {
  return (
    <div className="bg-ink-50 border border-ink-200 rounded-xl p-4">
      <div className="flex items-start gap-3">
        <Quote className="w-4 h-4 text-ink-400 flex-shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-ink-700 text-sm leading-relaxed italic">{passage.text}</p>
          <div className="flex items-center gap-3 mt-2">
            {passage.page_reference && (
              <span className="text-xs text-ink-400 font-medium">
                {passage.page_reference}
              </span>
            )}
            {passage.relevance && (
              <span className="text-xs text-ink-400 truncate">{passage.relevance}</span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

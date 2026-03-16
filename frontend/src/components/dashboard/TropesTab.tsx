"use client";
import { useState } from "react";
import type { TropeAnalysis } from "@/types/analysis";
import PassageCard from "@/components/ui/PassageCard";
import Badge from "@/components/ui/Badge";
import { getConfidenceColor } from "@/lib/utils";
import { ChevronDown, ChevronUp } from "lucide-react";

interface Props {
  tropes: TropeAnalysis[];
}

function TropeCard({ trope }: { trope: TropeAnalysis }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-white border border-ink-200 rounded-2xl overflow-hidden">
      <div
        className="p-6 cursor-pointer hover:bg-ink-50 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2 flex-wrap">
              <h3 className="font-serif text-xl text-ink-900">{trope.trope_name}</h3>
              <Badge className={getConfidenceColor(trope.confidence)}>
                {trope.confidence}
              </Badge>
            </div>
            <p className="text-ink-600 text-sm leading-relaxed">{trope.explanation}</p>

            {trope.related_characters.length > 0 && (
              <div className="flex flex-wrap gap-2 mt-3">
                {trope.related_characters.map((char) => (
                  <span
                    key={char}
                    className="text-xs bg-indigo-50 text-indigo-700 border border-indigo-200 px-2.5 py-1 rounded-full"
                  >
                    {char}
                  </span>
                ))}
              </div>
            )}
          </div>
          {expanded ? (
            <ChevronUp className="w-5 h-5 text-ink-400 flex-shrink-0 mt-1" />
          ) : (
            <ChevronDown className="w-5 h-5 text-ink-400 flex-shrink-0 mt-1" />
          )}
        </div>
      </div>

      {expanded && trope.supporting_passages.length > 0 && (
        <div className="border-t border-ink-100 p-6">
          <h4 className="text-xs font-semibold text-ink-400 uppercase tracking-wide mb-3">
            Supporting Passages
          </h4>
          <div className="space-y-3">
            {trope.supporting_passages.map((p, i) => (
              <PassageCard key={i} passage={p} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function TropesTab({ tropes }: Props) {
  return (
    <div className="space-y-4">
      <p className="text-ink-500 text-sm mb-6">
        Narrative tropes detected from a curated literary library.
        Confidence levels reflect how strongly the text supports each trope interpretation.
      </p>
      {tropes.map((trope, i) => (
        <TropeCard key={i} trope={trope} />
      ))}
    </div>
  );
}

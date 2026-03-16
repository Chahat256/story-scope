"use client";
import { useState } from "react";
import type { ThemeAnalysis } from "@/types/analysis";
import PassageCard from "@/components/ui/PassageCard";
import Badge from "@/components/ui/Badge";
import { getPrevalenceColor } from "@/lib/utils";
import { ChevronDown, ChevronUp } from "lucide-react";

interface Props {
  themes: ThemeAnalysis[];
}

function ThemeCard({ theme }: { theme: ThemeAnalysis }) {
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
              <h3 className="font-serif text-xl text-ink-900">{theme.theme}</h3>
              <Badge className={getPrevalenceColor(theme.prevalence)}>
                {theme.prevalence}
              </Badge>
            </div>
            <p className="text-ink-600 text-sm leading-relaxed">{theme.description}</p>
          </div>
          {expanded ? (
            <ChevronUp className="w-5 h-5 text-ink-400 flex-shrink-0 mt-1" />
          ) : (
            <ChevronDown className="w-5 h-5 text-ink-400 flex-shrink-0 mt-1" />
          )}
        </div>

        {/* Motifs */}
        {theme.motifs.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-4">
            {theme.motifs.map((motif) => (
              <span
                key={motif}
                className="text-xs bg-violet-50 text-violet-700 border border-violet-200 px-2.5 py-1 rounded-full"
              >
                {motif}
              </span>
            ))}
          </div>
        )}
      </div>

      {expanded && theme.supporting_passages.length > 0 && (
        <div className="border-t border-ink-100 p-6">
          <h4 className="text-xs font-semibold text-ink-400 uppercase tracking-wide mb-3">
            Supporting Passages
          </h4>
          <div className="space-y-3">
            {theme.supporting_passages.map((p, i) => (
              <PassageCard key={i} passage={p} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export default function ThemesTab({ themes }: Props) {
  return (
    <div className="space-y-4">
      <p className="text-ink-500 text-sm mb-6">
        Recurring themes and motifs identified through the text. The following interpretations
        are supported by evidence from the novel and presented as literary analysis, not objective fact.
      </p>
      {themes.map((theme, i) => (
        <ThemeCard key={i} theme={theme} />
      ))}
    </div>
  );
}

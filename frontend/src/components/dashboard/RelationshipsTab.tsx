"use client";
import { useState } from "react";
import type { RelationshipAnalysis } from "@/types/analysis";
import { getConfidenceColor } from "@/lib/utils";
import PassageCard from "@/components/ui/PassageCard";
import Badge from "@/components/ui/Badge";
import { ChevronDown, ChevronUp, ArrowLeftRight } from "lucide-react";

interface Props {
  relationships: RelationshipAnalysis[];
}

const RELATIONSHIP_COLORS: Record<string, string> = {
  friendship: "text-emerald-700 bg-emerald-50 border-emerald-200",
  rivalry: "text-orange-700 bg-orange-50 border-orange-200",
  romance: "text-rose-700 bg-rose-50 border-rose-200",
  family: "text-purple-700 bg-purple-50 border-purple-200",
  mentorship: "text-blue-700 bg-blue-50 border-blue-200",
  alliance: "text-teal-700 bg-teal-50 border-teal-200",
  conflict: "text-red-700 bg-red-50 border-red-200",
  complex: "text-slate-700 bg-slate-50 border-slate-200",
};

function RelationshipCard({ rel }: { rel: RelationshipAnalysis }) {
  const [expanded, setExpanded] = useState(false);
  const color = RELATIONSHIP_COLORS[rel.relationship_type] || RELATIONSHIP_COLORS.complex;

  return (
    <div className="bg-white border border-ink-200 rounded-2xl overflow-hidden">
      <div
        className="p-6 cursor-pointer hover:bg-ink-50 transition-colors"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-3 flex-wrap">
              <span className="font-serif text-lg text-ink-900">{rel.character_a}</span>
              <ArrowLeftRight className="w-4 h-4 text-ink-400" />
              <span className="font-serif text-lg text-ink-900">{rel.character_b}</span>
              <Badge className={color}>{rel.relationship_type}</Badge>
            </div>
            <p className="text-ink-600 text-sm leading-relaxed">{rel.description}</p>
          </div>
          {expanded ? (
            <ChevronUp className="w-5 h-5 text-ink-400 flex-shrink-0 mt-1" />
          ) : (
            <ChevronDown className="w-5 h-5 text-ink-400 flex-shrink-0 mt-1" />
          )}
        </div>
      </div>

      {expanded && (
        <div className="border-t border-ink-100 p-6 space-y-5">
          {rel.dynamics && (
            <div>
              <h4 className="text-xs font-semibold text-ink-400 uppercase tracking-wide mb-2">
                Relationship Dynamics
              </h4>
              <p className="text-ink-700 text-sm leading-relaxed">{rel.dynamics}</p>
            </div>
          )}

          {rel.supporting_passages.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-ink-400 uppercase tracking-wide mb-3">
                Supporting Passages
              </h4>
              <div className="space-y-3">
                {rel.supporting_passages.map((p, i) => (
                  <PassageCard key={i} passage={p} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function RelationshipsTab({ relationships }: Props) {
  return (
    <div className="space-y-4">
      <p className="text-ink-500 text-sm mb-6">
        Key relationships between major characters, identified through narrative analysis.
        Relationship types reflect the text&apos;s evidence, not absolute categorization.
      </p>
      {relationships.map((rel, i) => (
        <RelationshipCard key={i} rel={rel} />
      ))}
    </div>
  );
}

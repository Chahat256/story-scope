"use client";
import { useState } from "react";
import type { CharacterAnalysis } from "@/types/analysis";
import { getConfidenceColor, getRoleColor } from "@/lib/utils";
import PassageCard from "@/components/ui/PassageCard";
import Badge from "@/components/ui/Badge";
import { ChevronDown, ChevronUp } from "lucide-react";

interface Props {
  characters: CharacterAnalysis[];
}

function CharacterCard({ character }: { character: CharacterAnalysis }) {
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
              <h3 className="font-serif text-xl text-ink-900">{character.name}</h3>
              {character.aliases.length > 0 && (
                <span className="text-ink-400 text-sm">
                  aka {character.aliases.join(", ")}
                </span>
              )}
            </div>
            <div className="flex items-center gap-2 flex-wrap">
              <Badge className={getRoleColor(character.role)}>
                {character.role}
              </Badge>
              <Badge className={getConfidenceColor(character.confidence)}>
                {character.confidence} confidence
              </Badge>
            </div>
          </div>
          {expanded ? (
            <ChevronUp className="w-5 h-5 text-ink-400 flex-shrink-0 mt-1" />
          ) : (
            <ChevronDown className="w-5 h-5 text-ink-400 flex-shrink-0 mt-1" />
          )}
        </div>

        {/* Traits preview */}
        <div className="flex flex-wrap gap-2 mt-4">
          {character.defining_traits.slice(0, 4).map((trait) => (
            <span
              key={trait}
              className="text-xs bg-ink-100 text-ink-700 px-2.5 py-1 rounded-full"
            >
              {trait}
            </span>
          ))}
        </div>
      </div>

      {expanded && (
        <div className="border-t border-ink-100 p-6 space-y-6">
          {character.goals.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-ink-400 uppercase tracking-wide mb-2">
                Goals & Motivations
              </h4>
              <ul className="space-y-1">
                {character.goals.map((g, i) => (
                  <li key={i} className="text-ink-700 text-sm flex gap-2">
                    <span className="text-ink-300 mt-0.5">•</span>
                    {g}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {character.conflicts.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-ink-400 uppercase tracking-wide mb-2">
                Conflicts
              </h4>
              <ul className="space-y-1">
                {character.conflicts.map((c, i) => (
                  <li key={i} className="text-ink-700 text-sm flex gap-2">
                    <span className="text-ink-300 mt-0.5">•</span>
                    {c}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {character.important_relationships.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-ink-400 uppercase tracking-wide mb-2">
                Key Relationships
              </h4>
              <ul className="space-y-1">
                {character.important_relationships.map((r, i) => (
                  <li key={i} className="text-ink-700 text-sm flex gap-2">
                    <span className="text-ink-300 mt-0.5">→</span>
                    {r}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {character.supporting_passages.length > 0 && (
            <div>
              <h4 className="text-xs font-semibold text-ink-400 uppercase tracking-wide mb-3">
                Supporting Passages
              </h4>
              <div className="space-y-3">
                {character.supporting_passages.map((p, i) => (
                  <PassageCard key={i} passage={p} index={i} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function CharactersTab({ characters }: Props) {
  return (
    <div className="space-y-4">
      <p className="text-ink-500 text-sm mb-6">
        The following characters have been identified as having significant narrative presence.
        Analysis is based on textual evidence from the novel.
      </p>
      {characters.map((character) => (
        <CharacterCard key={character.name} character={character} />
      ))}
    </div>
  );
}

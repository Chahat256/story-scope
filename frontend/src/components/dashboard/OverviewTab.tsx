import type { AnalysisReport } from "@/types/analysis";
import { MapPin, Clock, Eye, Music } from "lucide-react";

interface Props {
  report: AnalysisReport;
}

export default function OverviewTab({ report }: Props) {
  const { overview } = report;

  return (
    <div className="space-y-8">
      {/* Summary */}
      <div className="bg-white border border-ink-200 rounded-2xl p-8">
        <h2 className="font-serif text-xl text-ink-900 mb-4">Narrative Summary</h2>
        <p className="text-ink-700 leading-relaxed text-lg italic">
          &ldquo;{overview.narrative_summary}&rdquo;
        </p>
      </div>

      {/* Details grid */}
      <div className="grid md:grid-cols-2 gap-4">
        {overview.setting_description && (
          <div className="bg-white border border-ink-200 rounded-xl p-5 flex gap-4">
            <div className="w-9 h-9 bg-blue-50 rounded-lg flex items-center justify-center flex-shrink-0">
              <MapPin className="w-4 h-4 text-blue-600" />
            </div>
            <div>
              <p className="text-xs font-medium text-ink-400 uppercase tracking-wide mb-1">Setting</p>
              <p className="text-ink-800 text-sm leading-relaxed">{overview.setting_description}</p>
            </div>
          </div>
        )}

        {overview.estimated_time_period && (
          <div className="bg-white border border-ink-200 rounded-xl p-5 flex gap-4">
            <div className="w-9 h-9 bg-amber-50 rounded-lg flex items-center justify-center flex-shrink-0">
              <Clock className="w-4 h-4 text-amber-600" />
            </div>
            <div>
              <p className="text-xs font-medium text-ink-400 uppercase tracking-wide mb-1">Time Period</p>
              <p className="text-ink-800 text-sm">{overview.estimated_time_period}</p>
            </div>
          </div>
        )}

        {overview.point_of_view && (
          <div className="bg-white border border-ink-200 rounded-xl p-5 flex gap-4">
            <div className="w-9 h-9 bg-violet-50 rounded-lg flex items-center justify-center flex-shrink-0">
              <Eye className="w-4 h-4 text-violet-600" />
            </div>
            <div>
              <p className="text-xs font-medium text-ink-400 uppercase tracking-wide mb-1">Point of View</p>
              <p className="text-ink-800 text-sm">{overview.point_of_view}</p>
            </div>
          </div>
        )}

        {overview.tone && (
          <div className="bg-white border border-ink-200 rounded-xl p-5 flex gap-4">
            <div className="w-9 h-9 bg-emerald-50 rounded-lg flex items-center justify-center flex-shrink-0">
              <Music className="w-4 h-4 text-emerald-600" />
            </div>
            <div>
              <p className="text-xs font-medium text-ink-400 uppercase tracking-wide mb-1">Tone</p>
              <p className="text-ink-800 text-sm">{overview.tone}</p>
            </div>
          </div>
        )}
      </div>

      {/* Quick stats */}
      <div className="bg-ink-950 text-parchment rounded-2xl p-8">
        <h3 className="font-serif text-lg text-ink-100 mb-6">Analysis at a glance</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6">
          {[
            { label: "Major Characters", value: report.characters.length },
            { label: "Relationships Mapped", value: report.relationships.length },
            { label: "Themes Identified", value: report.themes.length },
            { label: "Tropes Detected", value: report.tropes.length },
          ].map((stat) => (
            <div key={stat.label} className="text-center">
              <div className="font-serif text-4xl text-ink-100 mb-1">{stat.value}</div>
              <div className="text-ink-400 text-xs">{stat.label}</div>
            </div>
          ))}
        </div>
      </div>

      <p className="text-xs text-ink-400 text-center italic">
        This analysis represents likely interpretations supported by textual evidence. Literary analysis is inherently interpretive.
      </p>
    </div>
  );
}

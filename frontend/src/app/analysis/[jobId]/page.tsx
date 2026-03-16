"use client";
import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { BookOpen, Users, Heart, Lightbulb, Layers, MessageCircle, ArrowLeft } from "lucide-react";
import Link from "next/link";
import { getJobStatus, getReport } from "@/lib/api";
import ProcessingStatus from "@/components/upload/ProcessingStatus";
import OverviewTab from "@/components/dashboard/OverviewTab";
import CharactersTab from "@/components/dashboard/CharactersTab";
import RelationshipsTab from "@/components/dashboard/RelationshipsTab";
import ThemesTab from "@/components/dashboard/ThemesTab";
import TropesTab from "@/components/dashboard/TropesTab";
import ChatTab from "@/components/dashboard/ChatTab";
import type { AnalysisReport } from "@/types/analysis";

const TABS = [
  { id: "overview", label: "Overview", icon: BookOpen },
  { id: "characters", label: "Characters", icon: Users },
  { id: "relationships", label: "Relationships", icon: Heart },
  { id: "themes", label: "Themes", icon: Lightbulb },
  { id: "tropes", label: "Tropes", icon: Layers },
  { id: "chat", label: "Ask Questions", icon: MessageCircle },
];

export default function AnalysisPage() {
  const params = useParams();
  const jobId = params.jobId as string;
  const [activeTab, setActiveTab] = useState("overview");
  const [report, setReport] = useState<AnalysisReport | null>(null);

  // Poll job status
  const { data: status } = useQuery({
    queryKey: ["status", jobId],
    queryFn: () => getJobStatus(jobId),
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "complete" || status === "failed") return false;
      return 2000;
    },
    enabled: !!jobId,
  });

  // Fetch report when complete
  useEffect(() => {
    if (status?.status === "complete" && !report) {
      getReport(jobId).then(setReport).catch(console.error);
    }
  }, [status?.status, jobId, report]);

  const isComplete = status?.status === "complete";
  const isFailed = status?.status === "failed";

  return (
    <div className="min-h-screen bg-parchment">
      {/* Header */}
      <header className="border-b border-ink-200 bg-parchment/90 backdrop-blur-sm sticky top-0 z-20">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center gap-4">
          <Link
            href="/"
            className="flex items-center gap-2 text-ink-500 hover:text-ink-900 transition-colors text-sm"
          >
            <ArrowLeft className="w-4 h-4" />
            New analysis
          </Link>
          <div className="w-px h-4 bg-ink-300" />
          <div className="flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-ink-700" />
            <span className="font-serif text-lg text-ink-900">StoryScope</span>
          </div>
          {status?.filename && (
            <>
              <div className="w-px h-4 bg-ink-300" />
              <span className="text-ink-600 text-sm truncate max-w-48">
                {status.filename}
              </span>
            </>
          )}
        </div>
      </header>

      {/* Processing state */}
      {!isComplete && !isFailed && status && (
        <ProcessingStatus status={status} />
      )}

      {isFailed && (
        <div className="max-w-2xl mx-auto px-6 pt-20 text-center">
          <div className="bg-red-50 border border-red-200 rounded-2xl p-8">
            <h2 className="font-serif text-2xl text-red-800 mb-2">Analysis Failed</h2>
            <p className="text-red-600">{status?.message}</p>
            <Link href="/" className="mt-4 inline-block text-ink-700 underline text-sm">
              Try another file
            </Link>
          </div>
        </div>
      )}

      {/* Dashboard */}
      {isComplete && report && (
        <div className="max-w-7xl mx-auto px-6 py-8">
          {/* Title area */}
          <div className="mb-8">
            <h1 className="font-serif text-4xl text-ink-950 mb-2">
              {report.overview.title_guess}
            </h1>
            {report.overview.author_guess && (
              <p className="text-ink-500 text-lg">by {report.overview.author_guess}</p>
            )}
            <div className="flex items-center gap-3 mt-3">
              <span className="text-xs font-medium bg-ink-100 text-ink-700 px-3 py-1 rounded-full">
                {report.overview.genre_guess}
              </span>
              <span className="text-xs text-ink-400">
                {report.characters.length} major characters · {report.themes.length} themes · {report.tropes.length} tropes detected
              </span>
            </div>
          </div>

          {/* Tabs */}
          <div className="border-b border-ink-200 mb-8">
            <div className="flex gap-1 overflow-x-auto">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
                    activeTab === tab.id
                      ? "border-ink-800 text-ink-900"
                      : "border-transparent text-ink-500 hover:text-ink-800"
                  }`}
                >
                  <tab.icon className="w-4 h-4" />
                  {tab.label}
                </button>
              ))}
            </div>
          </div>

          {/* Tab content */}
          <div>
            {activeTab === "overview" && <OverviewTab report={report} />}
            {activeTab === "characters" && <CharactersTab characters={report.characters} />}
            {activeTab === "relationships" && <RelationshipsTab relationships={report.relationships} />}
            {activeTab === "themes" && <ThemesTab themes={report.themes} />}
            {activeTab === "tropes" && <TropesTab tropes={report.tropes} />}
            {activeTab === "chat" && <ChatTab jobId={jobId} />}
          </div>
        </div>
      )}
    </div>
  );
}

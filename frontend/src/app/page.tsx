"use client";
import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { BookOpen, FileText, Search, MessageCircle, Sparkles, ChevronRight } from "lucide-react";
import UploadZone from "@/components/upload/UploadZone";

export default function HomePage() {
  const router = useRouter();
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleJobCreated = useCallback(
    (jobId: string) => {
      router.push(`/analysis/${jobId}`);
    },
    [router]
  );

  return (
    <div className="min-h-screen bg-parchment">
      {/* Header */}
      <header className="border-b border-ink-200 bg-parchment/80 backdrop-blur-sm sticky top-0 z-10">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center gap-3">
          <BookOpen className="w-6 h-6 text-ink-700" />
          <span className="font-serif text-xl font-semibold text-ink-900">StoryScope</span>
          <span className="text-ink-400 text-sm ml-2">Literary Analysis</span>
        </div>
      </header>

      {/* Hero */}
      <section className="max-w-4xl mx-auto px-6 pt-20 pb-16 text-center">
        <div className="inline-flex items-center gap-2 bg-ink-100 text-ink-700 text-sm px-4 py-1.5 rounded-full mb-8 font-medium">
          <Sparkles className="w-4 h-4" />
          AI-Powered Literary Analysis
        </div>
        <h1 className="font-serif text-5xl md:text-6xl text-ink-950 mb-6 leading-tight">
          Understand any novel,
          <br />
          <em className="text-ink-600">deeply.</em>
        </h1>
        <p className="text-xl text-ink-600 max-w-2xl mx-auto mb-4 leading-relaxed">
          Upload a novel PDF and StoryScope automatically generates a structured literary
          analysis — characters, relationships, themes, tropes, and evidence-grounded insights.
        </p>
        <p className="text-sm text-ink-400 mb-16">
          Designed for English-language digital text novels. Not a generic PDF chatbot.
        </p>

        {/* Upload Zone */}
        <div className="max-w-2xl mx-auto">
          <UploadZone onJobCreated={handleJobCreated} />
        </div>
      </section>

      {/* Feature Grid */}
      <section className="max-w-6xl mx-auto px-6 pb-24">
        <h2 className="font-serif text-2xl text-ink-800 text-center mb-12">
          What StoryScope analyzes
        </h2>
        <div className="grid md:grid-cols-3 gap-6">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="bg-white border border-ink-200 rounded-xl p-6 hover:border-ink-400 transition-colors"
            >
              <div className="w-10 h-10 bg-ink-100 rounded-lg flex items-center justify-center mb-4">
                <f.icon className="w-5 h-5 text-ink-700" />
              </div>
              <h3 className="font-serif text-lg text-ink-900 mb-2">{f.title}</h3>
              <p className="text-ink-600 text-sm leading-relaxed">{f.description}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="bg-ink-950 text-parchment py-20 px-6">
        <div className="max-w-4xl mx-auto">
          <h2 className="font-serif text-3xl text-center mb-12 text-ink-50">
            How it works
          </h2>
          <div className="grid md:grid-cols-4 gap-6">
            {STEPS.map((step, i) => (
              <div key={i} className="text-center">
                <div className="w-10 h-10 bg-ink-700 rounded-full flex items-center justify-center mx-auto mb-3 text-ink-100 font-semibold text-sm">
                  {i + 1}
                </div>
                <h4 className="font-serif text-ink-100 mb-2">{step.title}</h4>
                <p className="text-ink-400 text-sm">{step.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-ink-200 py-8 px-6 text-center text-ink-400 text-sm">
        <div className="flex items-center justify-center gap-2">
          <BookOpen className="w-4 h-4" />
          <span>StoryScope — Literary Analysis for Novels</span>
        </div>
      </footer>
    </div>
  );
}

const FEATURES = [
  {
    icon: BookOpen,
    title: "Character Analysis",
    description:
      "Identify main characters with their defining traits, goals, conflicts, and key relationships — supported by passages from the text.",
  },
  {
    icon: Search,
    title: "Themes & Motifs",
    description:
      "Discover recurring themes and motifs woven through the narrative, grounded in textual evidence.",
  },
  {
    icon: Sparkles,
    title: "Trope Detection",
    description:
      "Identify multiple narrative tropes from a curated literary library, each with confidence levels and supporting passages.",
  },
  {
    icon: FileText,
    title: "Relationship Mapping",
    description:
      "Map the key relationships between major characters — friendships, rivalries, romances, conflicts — with explanation.",
  },
  {
    icon: ChevronRight,
    title: "Evidence-Grounded",
    description:
      "Every interpretation is backed by passages from the novel. No unsupported claims.",
  },
  {
    icon: MessageCircle,
    title: "Ask Questions",
    description:
      "After the analysis, ask follow-up questions about the novel. Answers are retrieval-grounded from the text.",
  },
];

const STEPS = [
  { title: "Upload", description: "Drop a digital novel PDF (up to 50MB)" },
  { title: "Extract", description: "Text is extracted and cleaned by page" },
  { title: "Analyze", description: "AI reads and generates structured analysis" },
  { title: "Explore", description: "Browse results and ask questions" },
];

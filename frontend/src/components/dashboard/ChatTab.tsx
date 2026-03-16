"use client";
import { useState, useRef, useEffect } from "react";
import { Send, Loader2, BookOpen } from "lucide-react";
import type { ChatMessage } from "@/types/analysis";
import { sendChatMessage } from "@/lib/api";
import PassageCard from "@/components/ui/PassageCard";

interface Props {
  jobId: string;
}

interface MessageWithSources extends ChatMessage {
  sources?: Array<{ text: string; page_reference: string | null; relevance: string }>;
}

export default function ChatTab({ jobId }: Props) {
  const [messages, setMessages] = useState<MessageWithSources[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMsg: MessageWithSources = { role: "user", content: input };
    const newMessages = [...messages, userMsg];
    setMessages(newMessages);
    setInput("");
    setIsLoading(true);

    try {
      const history = newMessages
        .slice(0, -1)
        .map(({ role, content }) => ({ role, content }));

      const result = await sendChatMessage(jobId, input, history);

      setMessages([
        ...newMessages,
        {
          role: "assistant",
          content: result.response,
          sources: result.sources,
        },
      ]);
    } catch (err) {
      setMessages([
        ...newMessages,
        {
          role: "assistant",
          content: "Sorry, I encountered an error. Please try again.",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto">
      <p className="text-ink-500 text-sm mb-6">
        Ask questions about the novel. Answers are grounded in retrieved passages from the text.
      </p>

      {/* Message area */}
      <div className="bg-white border border-ink-200 rounded-2xl overflow-hidden">
        <div className="min-h-96 max-h-[600px] overflow-y-auto p-6 space-y-6">
          {messages.length === 0 && (
            <div className="text-center py-16 text-ink-400">
              <BookOpen className="w-10 h-10 mx-auto mb-3 opacity-40" />
              <p className="text-sm">Ask anything about the novel.</p>
              <p className="text-xs mt-1">
                E.g. &ldquo;What motivates the protagonist?&rdquo; or &ldquo;How does the setting affect the story?&rdquo;
              </p>
            </div>
          )}

          {messages.map((msg, i) => (
            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`max-w-[85%] ${msg.role === "user" ? "order-2" : "order-1"}`}>
                <div
                  className={`rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                    msg.role === "user"
                      ? "bg-ink-900 text-parchment"
                      : "bg-ink-50 text-ink-800"
                  }`}
                >
                  {msg.content}
                </div>

                {msg.role === "assistant" && msg.sources && msg.sources.length > 0 && (
                  <div className="mt-3 space-y-2">
                    <p className="text-xs text-ink-400 font-medium px-1">Sources from the text:</p>
                    {msg.sources.slice(0, 2).map((src, j) => (
                      <PassageCard key={j} passage={src} />
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="flex justify-start">
              <div className="bg-ink-50 rounded-2xl px-4 py-3">
                <Loader2 className="w-4 h-4 text-ink-500 animate-spin" />
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="border-t border-ink-200 p-4">
          <div className="flex gap-3">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage()}
              placeholder="Ask about the novel..."
              className="flex-1 bg-ink-50 border border-ink-200 rounded-xl px-4 py-2.5 text-sm text-ink-900 placeholder-ink-400 focus:outline-none focus:border-ink-500 focus:ring-1 focus:ring-ink-500"
              disabled={isLoading}
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim() || isLoading}
              className="bg-ink-900 hover:bg-ink-700 disabled:opacity-50 disabled:cursor-not-allowed text-parchment rounded-xl px-4 py-2.5 transition-colors"
            >
              <Send className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

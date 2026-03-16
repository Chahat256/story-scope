"use client";
import { useCallback, useState, useRef } from "react";
import { Upload, FileText, AlertCircle, Loader2 } from "lucide-react";
import { uploadNovel } from "@/lib/api";
import { cn } from "@/lib/utils";

interface Props {
  onJobCreated: (jobId: string) => void;
}

export default function UploadZone({ onJobCreated }: Props) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = useCallback(
    async (file: File) => {
      setError(null);

      if (!file.name.toLowerCase().endsWith(".pdf")) {
        setError("Please upload a PDF file.");
        return;
      }

      const maxMB = 50;
      if (file.size > maxMB * 1024 * 1024) {
        setError(`File is too large. Maximum size is ${maxMB}MB.`);
        return;
      }

      setIsUploading(true);
      try {
        const result = await uploadNovel(file);
        onJobCreated(result.job_id);
      } catch (err: any) {
        const msg =
          err?.response?.data?.detail ||
          "Upload failed. Please try again.";
        setError(msg);
        setIsUploading(false);
      }
    },
    [onJobCreated]
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) handleFile(file);
    },
    [handleFile]
  );

  return (
    <div className="w-full">
      <div
        className={cn(
          "border-2 border-dashed rounded-2xl p-12 text-center cursor-pointer transition-all duration-200",
          isDragging
            ? "border-ink-600 bg-ink-50 scale-[1.01]"
            : "border-ink-300 bg-white hover:border-ink-500 hover:bg-ink-50",
          isUploading && "pointer-events-none opacity-70"
        )}
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) handleFile(file);
          }}
        />

        {isUploading ? (
          <div className="flex flex-col items-center gap-4">
            <Loader2 className="w-12 h-12 text-ink-600 animate-spin" />
            <p className="text-ink-700 font-medium">Uploading your novel...</p>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-4">
            <div className="w-16 h-16 bg-ink-100 rounded-2xl flex items-center justify-center">
              <Upload className="w-8 h-8 text-ink-600" />
            </div>
            <div>
              <p className="text-ink-900 font-semibold text-lg mb-1">
                Drop your novel PDF here
              </p>
              <p className="text-ink-500 text-sm">
                or click to browse — up to 50MB
              </p>
            </div>
            <div className="flex items-center gap-2 text-xs text-ink-400 bg-ink-50 px-4 py-2 rounded-full">
              <FileText className="w-3.5 h-3.5" />
              Best for digital text PDFs — not scanned images
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className="mt-4 flex items-start gap-3 bg-red-50 border border-red-200 rounded-xl p-4 text-sm text-red-700">
          <AlertCircle className="w-4 h-4 mt-0.5 flex-shrink-0" />
          {error}
        </div>
      )}
    </div>
  );
}

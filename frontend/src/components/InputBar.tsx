"use client";

import { useState, useRef, useCallback } from "react";
import { UploadedDocument } from "@/types";
import DocumentUpload, { ACCEPTED_TYPES } from "./DocumentUpload";

interface InputBarProps {
  onSubmit: (prompt: string, documentIds: string[]) => void;
  onUpload: (file: File) => Promise<UploadedDocument | null>;
  uploadedDocs: UploadedDocument[];
  onRemoveDoc: (docId: string) => void;
  isGenerating: boolean;
  isUploading: boolean;
  disabled: boolean;
}

export default function InputBar({
  onSubmit,
  onUpload,
  uploadedDocs,
  onRemoveDoc,
  isGenerating,
  isUploading,
  disabled,
}: InputBarProps) {
  const [prompt, setPrompt] = useState("");
  const [isDragOver, setIsDragOver] = useState(false);
  const dragCounterRef = useRef(0);

  const handleSubmit = () => {
    if (disabled || isGenerating) return;
    const documentIds = uploadedDocs.map((doc) => doc.id);
    if (documentIds.length === 0 && !prompt.trim()) return;
    onSubmit(prompt.trim(), documentIds);
    setPrompt("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const handleFileSelect = useCallback(
    async (file: File) => {
      await onUpload(file);
    },
    [onUpload]
  );

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current++;
    if (dragCounterRef.current === 1) {
      setIsDragOver(true);
    }
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current--;
    if (dragCounterRef.current === 0) {
      setIsDragOver(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current = 0;
    setIsDragOver(false);

    const files = e.dataTransfer.files;
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      if (ACCEPTED_TYPES.includes(file.type) || file.name.match(/\.(pdf|png|jpg|jpeg|gif|webp|txt|md|csv)$/i)) {
        await onUpload(file);
      }
    }
  };

  const canSubmit =
    !disabled &&
    !isGenerating &&
    (uploadedDocs.length > 0 || prompt.trim().length > 0);

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-40 bg-gradient-to-t from-[#090510]/95 via-[#0f0a1f]/72 to-transparent pt-7 pb-5 px-4"
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      <div className="max-w-3xl mx-auto relative">
        {/* Drag overlay */}
        {isDragOver && (
          <div className="absolute inset-0 -top-20 border-2 border-dashed border-fuchsia-300/70 bg-fuchsia-300/12 rounded-3xl flex items-center justify-center z-10 pointer-events-none backdrop-blur-md">
            <div className="text-fuchsia-100 font-medium text-lg">
              Drop files here
            </div>
          </div>
        )}

        {/* Uploaded document chips */}
        {uploadedDocs.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-2 px-1">
            {uploadedDocs.map((doc) => (
              <div
                key={doc.id}
                className="liquid-glass-chip flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm"
              >
                <svg
                  className="w-3.5 h-3.5 text-white/70 shrink-0"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                </svg>
                <span className="text-white/85 max-w-[150px] truncate">
                  {doc.filename}
                </span>
                <button
                  onClick={() => onRemoveDoc(doc.id)}
                  className="text-white/60 hover:text-white ml-0.5 cursor-pointer"
                >
                  <svg
                    className="w-3.5 h-3.5"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <line x1="18" y1="6" x2="6" y2="18" />
                    <line x1="6" y1="6" x2="18" y2="18" />
                  </svg>
                </button>
              </div>
            ))}
          </div>
        )}

        {/* Input container */}
        <div
          className={`
            liquid-glass-toolbar flex items-center gap-2 rounded-[1.6rem] px-4 py-3
            ring-1 ring-fuchsia-200/45
            shadow-[0_0_0_1px_rgba(248,205,255,0.25),0_22px_55px_rgba(123,29,180,0.45)]
            transition-colors duration-200
            ${isDragOver ? "border-fuchsia-200/70" : "border-white/30"}
            ${disabled ? "opacity-60" : ""}
          `}
        >
          <DocumentUpload
            onFileSelect={handleFileSelect}
            isUploading={isUploading}
            disabled={disabled}
          />

          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              disabled
                ? "Select a character to get started"
                : "Describe what you want to learn..."
            }
            disabled={disabled || isGenerating}
            rows={1}
            className={`flex-1 bg-transparent text-white placeholder:text-white/60 resize-none outline-none text-sm leading-6 max-h-32 min-h-[24px] ${prompt.length === 0 ? "text-center" : "text-left"}`}
            style={{ height: "24px" }}
            onInput={(e) => {
              const target = e.target as HTMLTextAreaElement;
              target.style.height = "24px";
              target.style.height = `${Math.min(target.scrollHeight, 128)}px`;
            }}
          />

          <button
            onClick={handleSubmit}
            disabled={!canSubmit}
            className={`
              p-2 rounded-xl transition-all duration-200 cursor-pointer
              ${
                canSubmit
                  ? "bg-gradient-to-br from-fuchsia-200 to-violet-300 text-violet-950 hover:from-fuchsia-100 hover:to-violet-200 shadow-[0_8px_20px_rgba(198,105,255,0.35)]"
                  : "bg-white/12 text-white/45 cursor-not-allowed border border-white/15"
              }
            `}
            title="Generate video"
          >
            {isGenerating ? (
              <svg
                className="w-4 h-4 animate-spin"
                viewBox="0 0 24 24"
                fill="none"
              >
                <circle
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="2"
                  className="opacity-25"
                />
                <path
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                  fill="currentColor"
                  className="opacity-75"
                />
              </svg>
            ) : (
              <svg
                className="w-4 h-4"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <line x1="12" y1="19" x2="12" y2="5" />
                <polyline points="5 12 12 5 19 12" />
              </svg>
            )}
          </button>
        </div>

      </div>
    </div>
  );
}

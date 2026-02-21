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
      className="fixed bottom-0 left-0 right-0 bg-gradient-to-t from-neutral-900 via-neutral-900 to-transparent pt-6 pb-4 px-4"
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDragOver={handleDragOver}
      onDrop={handleDrop}
    >
      <div className="max-w-3xl mx-auto relative">
        {/* Drag overlay */}
        {isDragOver && (
          <div className="absolute inset-0 -top-20 border-2 border-dashed border-blue-400 bg-blue-400/10 rounded-2xl flex items-center justify-center z-10 pointer-events-none">
            <div className="text-blue-400 font-medium text-lg">
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
                className="flex items-center gap-1.5 bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-sm"
              >
                <svg
                  className="w-3.5 h-3.5 text-neutral-400 shrink-0"
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
                <span className="text-neutral-300 max-w-[150px] truncate">
                  {doc.filename}
                </span>
                <button
                  onClick={() => onRemoveDoc(doc.id)}
                  className="text-neutral-500 hover:text-neutral-300 ml-0.5 cursor-pointer"
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
            flex items-end gap-2 bg-neutral-800 border rounded-2xl px-4 py-3
            transition-colors duration-200
            ${isDragOver ? "border-blue-400" : "border-neutral-700"}
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
            className="flex-1 bg-transparent text-white placeholder-neutral-500 resize-none outline-none text-sm leading-6 max-h-32 min-h-[24px]"
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
              p-2 rounded-lg transition-all duration-200 cursor-pointer
              ${
                canSubmit
                  ? "bg-white text-neutral-900 hover:bg-neutral-200"
                  : "bg-neutral-700 text-neutral-500 cursor-not-allowed"
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

        <p className="text-xs text-neutral-500 text-center mt-2">
          Upload documents and describe your topic. Jestify will generate an educational video.
        </p>
      </div>
    </div>
  );
}

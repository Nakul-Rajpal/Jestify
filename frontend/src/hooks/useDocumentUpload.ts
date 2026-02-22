"use client";

import { useState, useCallback } from "react";
import { uploadDocument } from "@/lib/api";
import { UploadedDocument } from "@/types";

interface UseDocumentUploadResult {
  upload: (file: File) => Promise<UploadedDocument | null>;
  isUploading: boolean;
  error: string | null;
}

const UPLOAD_TIMEOUT_MS = 120000;

export function useDocumentUpload(): UseDocumentUploadResult {
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const upload = useCallback(async (file: File): Promise<UploadedDocument | null> => {
    setIsUploading(true);
    setError(null);
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), UPLOAD_TIMEOUT_MS);

    try {
      const response = await uploadDocument(file, controller.signal);
      return {
        id: response.document_id,
        filename: response.filename,
        document_type: response.document_type,
        size_bytes: response.size_bytes,
      };
    } catch (err) {
      const message = err instanceof Error
        ? (
          err.name === "AbortError"
            ? "Upload timed out while extracting text. Try a smaller file."
            : err.message
        )
        : "Failed to upload document";
      setError(message);
      return null;
    } finally {
      clearTimeout(timeoutId);
      setIsUploading(false);
    }
  }, []);

  return { upload, isUploading, error };
}

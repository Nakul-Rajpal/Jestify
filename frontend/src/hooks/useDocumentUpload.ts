"use client";

import { useState, useCallback } from "react";
import { uploadDocument } from "@/lib/api";
import { UploadedDocument } from "@/types";

interface UseDocumentUploadResult {
  upload: (file: File) => Promise<UploadedDocument | null>;
  isUploading: boolean;
  error: string | null;
}

export function useDocumentUpload(): UseDocumentUploadResult {
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const upload = useCallback(async (file: File): Promise<UploadedDocument | null> => {
    setIsUploading(true);
    setError(null);

    try {
      const response = await uploadDocument(file);
      return {
        id: response.document_id,
        filename: response.filename,
        document_type: response.document_type,
        size_bytes: response.size_bytes,
      };
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to upload document";
      setError(message);
      return null;
    } finally {
      setIsUploading(false);
    }
  }, []);

  return { upload, isUploading, error };
}

"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { getJobStatus } from "@/lib/api";
import { JobStatus, JobStatusResponse } from "@/types";

interface UseJobPollingResult {
  status: JobStatus | null;
  progress: number;
  currentStep: string;
  videoUrl: string | null;
  thumbnailUrl: string | null;
  error: string | null;
  isPolling: boolean;
}

const POLL_INTERVAL = 3000;

export function useJobPolling(jobId: string | null): UseJobPollingResult {
  const [jobData, setJobData] = useState<JobStatusResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isPolling, setIsPolling] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setIsPolling(false);
  }, []);

  const poll = useCallback(
    async (id: string) => {
      try {
        const response = await getJobStatus(id);
        setJobData(response);
        setError(null);

        if (
          response.status === JobStatus.COMPLETED ||
          response.status === JobStatus.FAILED
        ) {
          stopPolling();
          if (response.status === JobStatus.FAILED) {
            setError(response.error_message || "Job failed");
          }
        }
      } catch (err) {
        const message =
          err instanceof Error ? err.message : "Failed to fetch job status";
        setError(message);
        stopPolling();
      }
    },
    [stopPolling]
  );

  useEffect(() => {
    if (!jobId) {
      stopPolling();
      setJobData(null);
      setError(null);
      return;
    }

    setIsPolling(true);
    setError(null);

    // Poll immediately
    poll(jobId);

    // Then poll on interval
    intervalRef.current = setInterval(() => {
      poll(jobId);
    }, POLL_INTERVAL);

    return () => {
      stopPolling();
    };
  }, [jobId, poll, stopPolling]);

  return {
    status: jobData?.status ?? null,
    progress: jobData?.progress_percent ?? 0,
    currentStep: jobData?.current_step ?? "",
    videoUrl: jobData?.video_url ?? null,
    thumbnailUrl: jobData?.thumbnail_url ?? null,
    error,
    isPolling,
  };
}

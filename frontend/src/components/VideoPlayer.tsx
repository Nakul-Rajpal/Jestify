"use client";

interface VideoPlayerProps {
  videoUrl: string;
  thumbnailUrl?: string | null;
  title?: string;
}

export default function VideoPlayer({
  videoUrl,
  thumbnailUrl,
  title = "Your Educational Video",
}: VideoPlayerProps) {
  return (
    <div className="w-full max-w-2xl mx-auto">
      {/* Video title */}
      <div className="mb-4">
        <h3 className="text-lg font-medium text-white">{title}</h3>
      </div>

      {/* Video player */}
      <div className="rounded-xl overflow-hidden bg-black border border-neutral-800">
        <video
          controls
          autoPlay
          className="w-full aspect-video"
          poster={thumbnailUrl || undefined}
          src={videoUrl}
        >
          <source src={videoUrl} type="video/mp4" />
          Your browser does not support the video tag.
        </video>
      </div>

      {/* Success message */}
      <div className="mt-4 text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-green-500/10 border border-green-500/20">
          <svg
            className="w-4 h-4 text-green-400"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="20 6 9 17 4 12" />
          </svg>
          <span className="text-sm text-green-400">Video generated successfully</span>
        </div>
      </div>
    </div>
  );
}

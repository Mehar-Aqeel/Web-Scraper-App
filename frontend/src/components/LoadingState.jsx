const STAGE_LABELS = {
  queued:           "Queued…",
  starting:         "Starting browser…",
  "launching browser": "Launching browser…",
  navigating:       "Navigating to page…",
  "waiting for JS": "Waiting for JavaScript…",
  "reading DOM":    "Reading DOM…",
  fetching:         "Fetching page…",
  extracting:       "Extracting data…",
  done:             "Done",
  error:            "Error",
};

export default function LoadingState({ stage = null, progress = null }) {
  const isJs = stage !== null && progress !== null;
  const label = isJs ? (STAGE_LABELS[stage] ?? stage) : "Extracting data…";

  return (
    <div role="status" aria-label={label} className="space-y-2">
      <div className="flex items-center gap-3 text-sm text-gray-600">
        <svg
          className="animate-spin h-5 w-5 shrink-0 text-blue-500"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
          aria-hidden="true"
        >
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
        </svg>
        <span>{label}</span>
        {isJs && (
          <span className="ml-auto text-xs text-gray-400 tabular-nums">{progress}%</span>
        )}
      </div>

      {isJs && (
        <div className="w-full bg-gray-200 rounded-full h-1.5" aria-hidden="true">
          <div
            className="bg-blue-500 h-1.5 rounded-full transition-all duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      )}
    </div>
  );
}

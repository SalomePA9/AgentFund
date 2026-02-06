interface ErrorMessageProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorMessage({ message, onRetry }: ErrorMessageProps) {
  return (
    <div role="alert" className="rounded-xl border border-error/30 bg-error-subtle p-6">
      <div className="flex items-start gap-3">
        <div className="w-5 h-5 mt-0.5 text-error flex-shrink-0">
          <svg aria-hidden="true" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </div>
        <div className="flex-1">
          <p className="text-sm text-error font-medium">Something went wrong</p>
          <p className="text-sm text-zinc-400 mt-1">{message}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="btn btn-secondary text-xs mt-3 py-1.5"
            >
              Try again
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

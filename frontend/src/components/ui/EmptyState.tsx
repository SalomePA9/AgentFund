import Link from 'next/link';

interface EmptyStateProps {
  icon?: React.ReactNode;
  title: string;
  description?: string;
  actionLabel?: string;
  actionHref?: string;
  onAction?: () => void;
}

export function EmptyState({
  icon,
  title,
  description,
  actionLabel,
  actionHref,
  onAction,
}: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 px-4">
      {icon && (
        <div className="w-16 h-16 rounded-full bg-background-tertiary flex items-center justify-center mb-4 text-zinc-400">
          {icon}
        </div>
      )}
      <h3 className="text-lg font-medium text-zinc-200 mb-1">{title}</h3>
      {description && (
        <p className="text-sm text-zinc-400 text-center max-w-sm mb-6">
          {description}
        </p>
      )}
      {actionLabel && actionHref && (
        <Link href={actionHref} className="btn btn-primary">
          {actionLabel}
        </Link>
      )}
      {actionLabel && onAction && !actionHref && (
        <button onClick={onAction} className="btn btn-primary">
          {actionLabel}
        </button>
      )}
    </div>
  );
}

import { cn } from '@/lib/utils';

type BadgeVariant = 'success' | 'warning' | 'error' | 'neutral' | 'accent';

interface BadgeProps {
  children: React.ReactNode;
  variant?: BadgeVariant;
  className?: string;
}

const variantClasses: Record<BadgeVariant, string> = {
  success: 'bg-success-subtle text-success',
  warning: 'bg-warning-subtle text-warning',
  error: 'bg-error-subtle text-error',
  neutral: 'bg-background-tertiary text-zinc-400',
  accent: 'bg-accent-subtle text-accent',
};

export function Badge({ children, variant = 'neutral', className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
        variantClasses[variant],
        className
      )}
    >
      {children}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const variant: BadgeVariant =
    status === 'active'
      ? 'success'
      : status === 'paused'
      ? 'warning'
      : status === 'stopped'
      ? 'error'
      : 'neutral';

  return <Badge variant={variant}>{status}</Badge>;
}

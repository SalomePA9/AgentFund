import { cn } from '@/lib/utils';

interface StatCardProps {
  label: string;
  value: string;
  change?: number;
  changeLabel?: string;
  subtitle?: string;
  valueClass?: string;
  icon?: React.ReactNode;
  loading?: boolean;
}

export function StatCard({
  label,
  value,
  change,
  changeLabel,
  subtitle,
  valueClass,
  icon,
  loading,
}: StatCardProps) {
  if (loading) {
    return (
      <div className="card">
        <div className="skeleton h-3 w-20 mb-2" />
        <div className="skeleton h-7 w-28 mb-1" />
        <div className="skeleton h-4 w-16" />
      </div>
    );
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-1">
        <div className="text-xs text-zinc-500 uppercase tracking-wide">
          {label}
        </div>
        {icon && <div className="text-zinc-500">{icon}</div>}
      </div>
      <div className={cn('text-2xl font-semibold text-number', valueClass)}>
        {value}
      </div>
      {change !== undefined && (
        <div
          className={cn(
            'text-sm mt-1',
            change > 0 ? 'text-success' : change < 0 ? 'text-error' : 'text-zinc-400'
          )}
        >
          {change > 0 ? '+' : ''}
          {change.toFixed(2)}%
          {changeLabel && <span className="text-zinc-500 ml-1">{changeLabel}</span>}
        </div>
      )}
      {subtitle && <div className="text-sm text-zinc-500 mt-1">{subtitle}</div>}
    </div>
  );
}

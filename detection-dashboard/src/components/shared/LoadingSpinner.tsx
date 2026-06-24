import { cn } from '@/lib/utils';
import { Loader2 } from 'lucide-react';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  label?: string;
}

const sizeMap: Record<string, string> = {
  sm: 'w-4 h-4',
  md: 'w-8 h-8',
  lg: 'w-12 h-12',
};

export function LoadingSpinner({ size = 'md', className, label }: LoadingSpinnerProps) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-12">
      <Loader2
        className={cn('animate-spin text-ueba-accent-blue', sizeMap[size], className)}
      />
      {label && (
        <p className="text-sm text-ueba-text-muted">{label}</p>
      )}
    </div>
  );
}

export function PageLoading() {
  return (
    <div className="flex items-center justify-center h-64">
      <LoadingSpinner size="lg" label="Loading..." />
    </div>
  );
}

export function InlineLoading() {
  return (
    <div className="flex items-center justify-center py-8">
      <LoadingSpinner size="sm" label="Fetching data..." />
    </div>
  );
}

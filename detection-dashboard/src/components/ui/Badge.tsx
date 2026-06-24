import * as React from 'react';
import { cn } from '@/lib/utils';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info';
}

const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className, variant = 'default', ...props }, ref) => {
    const variants: Record<string, string> = {
      default: 'bg-ueba-cardhover text-ueba-text-secondary',
      success: 'bg-emerald-500/10 text-ueba-accent-green border-emerald-500/30',
      warning: 'bg-yellow-500/10 text-ueba-accent-yellow border-yellow-500/30',
      danger: 'bg-red-500/10 text-ueba-accent-red border-red-500/30',
      info: 'bg-blue-500/10 text-ueba-accent-blue border-blue-500/30',
    };

    return (
      <span
        ref={ref}
        className={cn(
          'inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium',
          variants[variant],
          className
        )}
        {...props}
      />
    );
  }
);
Badge.displayName = 'Badge';

export { Badge };

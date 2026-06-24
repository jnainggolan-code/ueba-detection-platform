import React from 'react';
import { cn } from '@/lib/utils';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  icon?: React.ReactNode;
}

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ className, icon, ...props }, ref) => {
    return (
      <div className="relative">
        {icon && (
          <div className="absolute inset-y-0 left-0 flex items-center pl-3 pointer-events-none text-ueba-text-muted">
            {icon}
          </div>
        )}
        <input
          ref={ref}
          className={cn(
            'w-full rounded-md border border-ueba-border bg-ueba-bg-deep px-3 py-2 text-sm text-ueba-text-primary placeholder:text-ueba-text-muted focus:outline-none focus:ring-2 focus:ring-ueba-accent-blue focus:border-transparent transition-colors disabled:opacity-50 disabled:cursor-not-allowed',
            icon && 'pl-10',
            className
          )}
          {...props}
        />
      </div>
    );
  }
);
Input.displayName = 'Input';

export { Input };

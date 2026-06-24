import * as React from 'react';
import { cn } from '@/lib/utils';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'destructive' | 'outline' | 'ghost' | 'link';
  size?: 'sm' | 'md' | 'lg';
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'md', ...props }, ref) => {
    const variants: Record<string, string> = {
      default:
        'bg-ueba-accent-blue text-white hover:bg-blue-600 active:bg-blue-700',
      destructive:
        'bg-ueba-accent-red text-white hover:bg-red-600 active:bg-red-700',
      outline:
        'border border-ueba-border bg-transparent hover:bg-ueba-cardhover text-ueba-text-primary',
      ghost:
        'bg-transparent hover:bg-ueba-cardhover text-ueba-text-primary',
      link:
        'bg-transparent underline-offset-4 hover:underline text-ueba-accent-blue',
    };

    const sizes: Record<string, string> = {
      sm: 'h-8 px-3 text-xs rounded',
      md: 'h-10 px-4 text-sm rounded-md',
      lg: 'h-12 px-6 text-base rounded-lg',
    };

    return (
      <button
        className={cn(
          'inline-flex items-center justify-center font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ueba-accent-blue focus-visible:ring-offset-2 focus-visible:ring-offset-ueba-bg disabled:opacity-50 disabled:pointer-events-none',
          variants[variant],
          sizes[size],
          className
        )}
        ref={ref}
        {...props}
      />
    );
  }
);
Button.displayName = 'Button';

export { Button };

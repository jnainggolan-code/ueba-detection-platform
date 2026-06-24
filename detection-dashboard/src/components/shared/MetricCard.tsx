import { cn } from '@/lib/utils';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';

interface MetricCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon?: React.ReactNode;
  trend?: 'up' | 'down' | 'stable';
  trendValue?: string;
  accent?: 'green' | 'red' | 'blue' | 'yellow' | 'purple';
  loading?: boolean;
  className?: string;
}

const accentColors: Record<string, string> = {
  green: 'border-l-ueba-accent-green',
  red: 'border-l-ueba-accent-red',
  blue: 'border-l-ueba-accent-blue',
  yellow: 'border-l-ueba-accent-yellow',
  purple: 'border-l-ueba-accent-purple',
};

const accentText: Record<string, string> = {
  green: 'text-ueba-accent-green',
  red: 'text-ueba-accent-red',
  blue: 'text-ueba-accent-blue',
  yellow: 'text-ueba-accent-yellow',
  purple: 'text-ueba-accent-purple',
};

const accentBg: Record<string, string> = {
  green: 'bg-emerald-500/10',
  red: 'bg-red-500/10',
  blue: 'bg-blue-500/10',
  yellow: 'bg-yellow-500/10',
  purple: 'bg-purple-500/10',
};

export function MetricCard({
  title,
  value,
  subtitle,
  icon,
  trend,
  trendValue,
  accent = 'blue',
  loading = false,
  className,
}: MetricCardProps) {
  const TrendIcon = trend === 'up' ? TrendingUp : trend === 'down' ? TrendingDown : Minus;
  const trendColor = trend === 'up' ? 'text-ueba-accent-green' : trend === 'down' ? 'text-ueba-accent-red' : 'text-ueba-text-muted';

  if (loading) {
    return (
      <Card className={cn('border-l-4', accentColors[accent], className)}>
        <CardHeader>
          <CardTitle className="text-sm text-ueba-text-muted">{title}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-8 w-24 bg-ueba-cardhover rounded animate-pulse" />
          <div className="h-4 w-32 bg-ueba-cardhover rounded animate-pulse mt-2" />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className={cn('border-l-4', accentColors[accent], className)}>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="text-sm text-ueba-text-muted font-medium">{title}</CardTitle>
        {icon && (
          <div className={cn('p-2 rounded-lg', accentBg[accent])}>
            <div className={cn('w-4 h-4', accentText[accent])}>{icon}</div>
          </div>
        )}
      </CardHeader>
      <CardContent>
        <div className="flex items-baseline gap-2">
          <span className="text-2xl font-bold text-ueba-text-primary font-mono">{value}</span>
          {trend && trendValue && (
            <span className={cn('flex items-center gap-0.5 text-xs font-medium', trendColor)}>
              <TrendIcon className="w-3 h-3" />
              {trendValue}
            </span>
          )}
        </div>
        {subtitle && (
          <p className="text-xs text-ueba-text-muted mt-1">{subtitle}</p>
        )}
      </CardContent>
    </Card>
  );
}

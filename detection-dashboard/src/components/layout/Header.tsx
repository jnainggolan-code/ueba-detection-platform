import { Bell, Search } from 'lucide-react';
import { Input } from '@/components/ui/Input';

interface HeaderProps {
  title: string;
  onSearch?: (query: string) => void;
  searchPlaceholder?: string;
}

export function Header({ title, onSearch, searchPlaceholder }: HeaderProps) {
  return (
    <header className="h-16 border-b border-ueba-border bg-ueba-bg flex items-center justify-between px-6">
      <div>
        <h1 className="text-lg font-bold text-ueba-text-primary">{title}</h1>
      </div>

      <div className="flex items-center gap-4">
        {onSearch && (
          <div className="hidden md:block w-72">
            <Input
              icon={<Search className="w-4 h-4" />}
              placeholder={searchPlaceholder ?? 'Search...'}
              onChange={(e) => onSearch(e.target.value)}
            />
          </div>
        )}

        {/* Alert bell with badge */}
        <button className="relative p-2 rounded-lg text-ueba-text-muted hover:text-ueba-text-primary hover:bg-ueba-card transition-colors">
          <Bell className="w-5 h-5" />
          <span className="absolute top-1 right-1 w-2 h-2 bg-ueba-accent-red rounded-full" />
        </button>

        {/* User avatar */}
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-full bg-ueba-accent-blue/20 flex items-center justify-center">
            <span className="text-xs font-bold text-ueba-accent-blue">SA</span>
          </div>
          <div className="hidden sm:block">
            <p className="text-xs font-medium text-ueba-text-primary">Security Analyst</p>
            <p className="text-[10px] text-ueba-text-muted">Online</p>
          </div>
        </div>
      </div>
    </header>
  );
}

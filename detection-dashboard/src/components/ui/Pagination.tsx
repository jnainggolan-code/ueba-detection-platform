import { cn } from '@/lib/utils';

interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  /** Cursor-based navigation */
  hasMore?: boolean;
  hasPrev?: boolean;
  onNext?: () => void;
  onPrev?: () => void;
}

export function Pagination({
  currentPage,
  totalPages,
  onPageChange,
  hasMore = false,
  hasPrev = false,
  onNext,
  onPrev,
}: PaginationProps) {
  // If cursor-based navigation is available, use it
  if (onNext || onPrev) {
    return (
      <div className="flex items-center justify-center gap-1 mt-4">
        <button
          onClick={onPrev}
          disabled={!hasPrev}
          className={cn(
            'px-3 py-1.5 text-xs rounded border border-ueba-border transition-colors',
            !hasPrev
              ? 'text-ueba-text-muted cursor-not-allowed opacity-50'
              : 'text-ueba-text-secondary hover:bg-ueba-cardhover hover:text-ueba-text-primary'
          )}
        >
          ← Prev
        </button>

        <span className="px-3 py-1.5 text-xs text-ueba-text-muted">
          Page {currentPage}
          {totalPages > 0 && ` of ${totalPages.toLocaleString()}`}
        </span>

        <button
          onClick={onNext}
          disabled={!hasMore}
          className={cn(
            'px-3 py-1.5 text-xs rounded border border-ueba-border transition-colors',
            !hasMore
              ? 'text-ueba-text-muted cursor-not-allowed opacity-50'
              : 'text-ueba-text-secondary hover:bg-ueba-cardhover hover:text-ueba-text-primary'
          )}
        >
          Next →
        </button>
      </div>
    );
  }

  // Fallback: page-based pagination (original)
  const pages = getPageNumbers(currentPage, totalPages);

  if (totalPages <= 1) return null;

  return (
    <div className="flex items-center justify-center gap-1 mt-4">
      <button
        onClick={() => onPageChange(currentPage - 1)}
        disabled={currentPage <= 1}
        className={cn(
          'px-3 py-1.5 text-xs rounded border border-ueba-border transition-colors',
          currentPage <= 1
            ? 'text-ueba-text-muted cursor-not-allowed opacity-50'
            : 'text-ueba-text-secondary hover:bg-ueba-cardhover hover:text-ueba-text-primary'
        )}
      >
        Prev
      </button>

      {pages.map((page, idx) => {
        if (page === '...') {
          return (
            <span key={`ellipsis-${idx}`} className="px-2 text-ueba-text-muted text-xs">
              ...
            </span>
          );
        }
        return (
          <button
            key={page}
            onClick={() => onPageChange(page as number)}
            className={cn(
              'px-3 py-1.5 text-xs rounded border transition-colors',
              currentPage === page
                ? 'bg-ueba-accent-blue text-white border-ueba-accent-blue'
                : 'border-ueba-border text-ueba-text-secondary hover:bg-ueba-cardhover'
            )}
          >
            {page}
          </button>
        );
      })}

      <button
        onClick={() => onPageChange(currentPage + 1)}
        disabled={currentPage >= totalPages}
        className={cn(
          'px-3 py-1.5 text-xs rounded border border-ueba-border transition-colors',
          currentPage >= totalPages
            ? 'text-ueba-text-muted cursor-not-allowed opacity-50'
            : 'text-ueba-text-secondary hover:bg-ueba-cardhover hover:text-ueba-text-primary'
        )}
      >
        Next
      </button>
    </div>
  );
}

function getPageNumbers(current: number, total: number): (number | '...')[] {
  if (total <= 7) {
    return Array.from({ length: total }, (_, i) => i + 1);
  }

  const pages: (number | '...')[] = [1];

  if (current > 3) pages.push('...');

  const start = Math.max(2, current - 1);
  const end = Math.min(total - 1, current + 1);

  for (let i = start; i <= end; i++) {
    pages.push(i);
  }

  if (current < total - 2) pages.push('...');

  pages.push(total);

  return pages;
}

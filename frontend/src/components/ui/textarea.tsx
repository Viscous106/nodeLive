import type { TextareaHTMLAttributes } from 'react'

import { cn } from '@/lib/utils'

export function Textarea({
  className,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        'w-full rounded-btn border border-border bg-card px-3 py-2 text-sm text-text-primary',
        'placeholder:text-text-muted transition-colors',
        'focus-visible:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30',
        'disabled:cursor-not-allowed disabled:opacity-50',
        className,
      )}
      {...props}
    />
  )
}

import type { HTMLAttributes } from 'react'

import { cn } from '@/lib/utils'

type Variant =
  | 'default'
  | 'mandatory'
  | 'new'
  | 'unsolved'
  | 'success'
  | 'warning'
  | 'danger'

const VARIANTS: Record<Variant, string> = {
  default: 'bg-border-muted text-text-secondary',
  mandatory: 'bg-badge-mandatory-bg text-badge-mandatory-text',
  new: 'bg-badge-new-bg text-badge-new-text',
  unsolved: 'bg-badge-unsolved-bg text-badge-unsolved-text',
  success: 'bg-success-light/15 text-success',
  warning: 'bg-warning/10 text-warning',
  danger: 'bg-danger/10 text-danger',
}

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: Variant
}

export function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-badge px-2 py-0.5 text-xs font-semibold leading-none',
        VARIANTS[variant],
        className,
      )}
      {...props}
    />
  )
}

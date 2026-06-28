import { GraduationCap } from 'lucide-react'
import type { ReactNode } from 'react'

export function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string
  subtitle: string
  children: ReactNode
  footer: ReactNode
}) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-page px-4 py-12">
      <div className="mb-6 flex items-center gap-2">
        <span className="flex h-9 w-9 items-center justify-center rounded-md bg-primary text-white">
          <GraduationCap className="h-6 w-6" />
        </span>
        <span className="text-xl font-bold text-text-primary">nodeLive</span>
      </div>

      <div className="w-full max-w-[420px] rounded-card border border-border bg-card p-6 shadow-card sm:p-8">
        <h1 className="text-2xl font-bold text-text-primary">{title}</h1>
        <p className="mt-1 text-sm text-text-muted">{subtitle}</p>
        <div className="mt-6">{children}</div>
      </div>

      <p className="mt-6 text-sm text-text-secondary">{footer}</p>
    </div>
  )
}

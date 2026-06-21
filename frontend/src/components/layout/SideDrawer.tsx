import { BarChart2, Calendar, House, Shield, Trophy, X } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { useEffect, useRef } from 'react'
import { NavLink } from 'react-router-dom'

import { useAuth } from '@/hooks/useAuth'
import { cn } from '@/lib/utils'
import { useUiStore } from '@/stores/uiStore'

interface NavItem {
  to: string
  label: string
  icon: LucideIcon
}

const PRIMARY: NavItem[] = [{ to: '/dashboard', label: 'Home', icon: House }]

const LEARN: NavItem[] = [
  { to: '/sessions', label: 'Sessions', icon: Calendar },
  { to: '/progress', label: 'My Progress', icon: BarChart2 },
  { to: '/leaderboard', label: 'Leaderboard', icon: Trophy },
]

function DrawerLink({ item, onNavigate }: { item: NavItem; onNavigate: () => void }) {
  const Icon = item.icon
  return (
    <NavLink
      to={item.to}
      onClick={onNavigate}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
          isActive
            ? 'bg-primary/10 text-primary'
            : 'text-text-secondary hover:bg-border-muted',
        )
      }
    >
      <Icon className="h-5 w-5" />
      {item.label}
    </NavLink>
  )
}

export function SideDrawer() {
  const open = useUiStore((s) => s.drawerOpen)
  const close = useUiStore((s) => s.closeDrawer)
  const { user } = useAuth()
  const closeRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!open) return
    const previouslyFocused = document.activeElement as HTMLElement | null
    closeRef.current?.focus()
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') close()
    }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
      previouslyFocused?.focus()
    }
  }, [open, close])

  return (
    <>
      {/* Backdrop */}
      <div
        aria-hidden={!open}
        onClick={close}
        className={cn(
          'fixed inset-0 z-40 bg-black/40 transition-opacity duration-200',
          open ? 'opacity-100' : 'pointer-events-none opacity-0',
        )}
      />
      {/* Panel */}
      <aside
        role="dialog"
        aria-label="Navigation"
        aria-modal="true"
        hidden={!open}
        className={cn(
          'fixed left-0 top-0 z-50 flex h-full w-[290px] flex-col bg-card shadow-drawer transition-transform duration-200 ease-in-out',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="flex h-16 items-center justify-between border-b border-border px-4">
          <span className="text-base font-bold text-text-primary">linkHQ</span>
          <button
            ref={closeRef}
            type="button"
            onClick={close}
            aria-label="Close menu"
            className="rounded-btn p-2 text-text-secondary hover:bg-border-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          {PRIMARY.map((item) => (
            <DrawerLink key={item.to} item={item} onNavigate={close} />
          ))}

          <p className="px-3 pb-1 pt-4 text-xs font-semibold uppercase tracking-wide text-text-muted">
            Learn and Practice
          </p>
          {LEARN.map((item) => (
            <DrawerLink key={item.to} item={item} onNavigate={close} />
          ))}

          {user?.role === 'ADMIN' && (
            <>
              <p className="px-3 pb-1 pt-4 text-xs font-semibold uppercase tracking-wide text-text-muted">
                Manage
              </p>
              <DrawerLink
                item={{ to: '/admin', label: 'Admin', icon: Shield }}
                onNavigate={close}
              />
            </>
          )}
        </nav>
      </aside>
    </>
  )
}

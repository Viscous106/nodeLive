import { Bell, BellOff, ChevronDown, Coins, GraduationCap, LogOut, Menu, Moon, Settings, Sun } from 'lucide-react'
import { Link, useNavigate } from 'react-router-dom'

import { Avatar } from '@/components/ui/avatar'
import { DropdownItem, DropdownMenu } from '@/components/ui/dropdown-menu'
import { useAuth, useLogout } from '@/hooks/useAuth'
import { useThemeStore } from '@/stores/themeStore'
import { useUiStore } from '@/stores/uiStore'

export function TopNav() {
  const openDrawer = useUiStore((s) => s.openDrawer)
  const { user } = useAuth()
  const logout = useLogout()
  const navigate = useNavigate()
  const { dark, toggle } = useThemeStore()

  return (
    <header className="sticky top-0 z-40 flex h-16 items-center justify-between border-b border-border bg-card px-4 sm:px-page-x">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={openDrawer}
          aria-label="Open menu"
          className="rounded-btn p-2 text-text-secondary hover:bg-border-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
        >
          <Menu className="h-5 w-5" />
        </button>
        <Link to="/dashboard" className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-md bg-primary text-white">
            <GraduationCap className="h-5 w-5" />
          </span>
          <span className="text-lg font-bold text-text-primary">nodeLive</span>
        </Link>
      </div>

      <div className="flex items-center gap-2 sm:gap-4">
        {user && (
          <span
            className="hidden items-center gap-1.5 rounded-pill border border-gold-border px-3 py-1 text-sm font-semibold text-gold-border sm:inline-flex"
            title="Your coins"
          >
            <Coins className="h-4 w-4" aria-hidden="true" />
            {user.coins}
            <span className="sr-only">coins</span>
          </span>
        )}
        <button
          type="button"
          onClick={toggle}
          aria-label={dark ? 'Switch to light mode' : 'Switch to dark mode'}
          className="rounded-full p-2 text-text-secondary hover:bg-border-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
        >
          {dark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </button>
        <DropdownMenu
          label="Notifications"
          align="right"
          trigger={
            <span className="rounded-full p-2 text-text-secondary hover:bg-border-muted">
              <Bell className="h-5 w-5" />
            </span>
          }
        >
          <div className="border-b border-border px-3 py-2 text-sm font-semibold text-text-primary">
            Notifications
          </div>
          <div className="flex flex-col items-center py-4 text-xs text-text-muted">
            <BellOff className="mb-2 h-5 w-5 opacity-40" />
            No notifications yet.
          </div>
        </DropdownMenu>

        {user && (
          <DropdownMenu
            label="Account menu"
            trigger={
              <span className="flex items-center gap-2 rounded-pill py-1 pl-1 pr-2 hover:bg-border-muted">
                <Avatar name={user.displayName} src={user.avatarUrl} />
                <span className="hidden text-sm font-medium text-text-primary sm:inline">
                  {user.displayName}
                </span>
                <ChevronDown className="h-4 w-4 text-text-muted" />
              </span>
            }
          >
            <div className="border-b border-border px-3 py-2">
              <p className="truncate text-sm font-semibold text-text-primary">
                {user.displayName}
              </p>
              <p className="truncate text-xs text-text-muted">{user.email}</p>
            </div>
            <DropdownItem onClick={() => navigate('/settings')}>
              <Settings className="h-4 w-4" />
              Settings
            </DropdownItem>
            <DropdownItem
              onClick={() => logout.mutate()}
              className="text-danger hover:bg-danger/5"
            >
              <LogOut className="h-4 w-4" />
              Log out
            </DropdownItem>
          </DropdownMenu>
        )}
      </div>
    </header>
  )
}

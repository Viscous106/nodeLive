import { Navigate, Outlet } from 'react-router-dom'

import { Spinner } from '@/components/ui/spinner'
import { useAuth } from '@/hooks/useAuth'

function FullScreenLoader() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-page">
      <Spinner className="h-8 w-8 text-primary" />
    </div>
  )
}

/** Gate for authenticated routes. Sends anonymous users to /login. */
export function ProtectedRoute() {
  const { isLoading, isAuthenticated } = useAuth()
  if (isLoading) return <FullScreenLoader />
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return <Outlet />
}

/** Gate for login/signup. Sends already-authenticated users to the dashboard. */
export function PublicOnlyRoute() {
  const { isLoading, isAuthenticated } = useAuth()
  if (isLoading) return <FullScreenLoader />
  if (isAuthenticated) return <Navigate to="/dashboard" replace />
  return <Outlet />
}

/** Gate for admin-only routes. Non-admins are bounced to the dashboard. */
export function AdminRoute() {
  const { isLoading, user } = useAuth()
  if (isLoading) return <FullScreenLoader />
  if (!user) return <Navigate to="/login" replace />
  if (user.role !== 'ADMIN') return <Navigate to="/dashboard" replace />
  return <Outlet />
}

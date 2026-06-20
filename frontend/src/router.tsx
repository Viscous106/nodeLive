import { lazy, Suspense } from 'react'
import type { ReactNode } from 'react'
import { createBrowserRouter, Navigate } from 'react-router-dom'

import { ProtectedRoute, PublicOnlyRoute } from '@/components/auth/guards'
import { PageLoader } from '@/components/ui/PageLoader'

const LoginPage = lazy(() => import('@/pages/LoginPage'))
const SignupPage = lazy(() => import('@/pages/SignupPage'))
const DashboardPage = lazy(() => import('@/pages/DashboardPage'))
const SessionDetailPage = lazy(() => import('@/pages/SessionDetailPage'))
const LiveMeetingPage = lazy(() => import('@/pages/LiveMeetingPage'))
const NotFoundPage = lazy(() => import('@/pages/NotFoundPage'))

function Lazy({ children }: { children: ReactNode }) {
  return <Suspense fallback={<PageLoader />}>{children}</Suspense>
}

export const router = createBrowserRouter([
  { path: '/', element: <Navigate to="/dashboard" replace /> },
  {
    element: <PublicOnlyRoute />,
    children: [
      { path: '/login', element: <Lazy><LoginPage /></Lazy> },
      { path: '/signup', element: <Lazy><SignupPage /></Lazy> },
    ],
  },
  {
    element: <ProtectedRoute />,
    children: [
      { path: '/dashboard', element: <Lazy><DashboardPage /></Lazy> },
      { path: '/session/:sessionId', element: <Lazy><SessionDetailPage /></Lazy> },
      { path: '/live/:sessionId', element: <Lazy><LiveMeetingPage /></Lazy> },
    ],
  },
  { path: '*', element: <Lazy><NotFoundPage /></Lazy> },
])

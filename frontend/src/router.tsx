import { lazy, Suspense } from 'react'
import type { ReactNode } from 'react'
import { createBrowserRouter, Navigate } from 'react-router-dom'

import {
  AdminRoute,
  ProtectedRoute,
  PublicOnlyRoute,
} from '@/components/auth/guards'
import { PageLoader } from '@/components/ui/PageLoader'

const LoginPage = lazy(() => import('@/pages/LoginPage'))
const SignupPage = lazy(() => import('@/pages/SignupPage'))
const DashboardPage = lazy(() => import('@/pages/DashboardPage'))
const SessionsPage = lazy(() => import('@/pages/SessionsPage'))
const LeaderboardPage = lazy(() => import('@/pages/LeaderboardPage'))
const SessionDetailPage = lazy(() => import('@/pages/SessionDetailPage'))
const LiveMeetingPage = lazy(() => import('@/pages/LiveMeetingPage'))
const RecordingPlayerPage = lazy(() => import('@/pages/RecordingPlayerPage'))
const AdminPage = lazy(() => import('@/pages/AdminPage'))
const ProgressPage = lazy(() => import('@/pages/ProgressPage'))
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
      { path: '/sessions', element: <Lazy><SessionsPage /></Lazy> },
      { path: '/leaderboard', element: <Lazy><LeaderboardPage /></Lazy> },
      { path: '/session/:sessionId', element: <Lazy><SessionDetailPage /></Lazy> },
      { path: '/live/:sessionId', element: <Lazy><LiveMeetingPage /></Lazy> },
      { path: '/session/:sessionId/recording', element: <Lazy><RecordingPlayerPage /></Lazy> },
      { path: '/progress', element: <Lazy><ProgressPage /></Lazy> },
    ],
  },
  {
    element: <AdminRoute />,
    children: [
      { path: '/admin', element: <Lazy><AdminPage /></Lazy> },
    ],
  },
  { path: '*', element: <Lazy><NotFoundPage /></Lazy> },
])

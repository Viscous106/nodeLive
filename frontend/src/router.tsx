import { createBrowserRouter, Navigate } from 'react-router-dom'

import { ProtectedRoute, PublicOnlyRoute } from '@/components/auth/guards'
import DashboardPage from '@/pages/DashboardPage'
import LoginPage from '@/pages/LoginPage'
import NotFoundPage from '@/pages/NotFoundPage'
import SessionDetailPage from '@/pages/SessionDetailPage'
import SignupPage from '@/pages/SignupPage'

export const router = createBrowserRouter([
  { path: '/', element: <Navigate to="/dashboard" replace /> },
  {
    element: <PublicOnlyRoute />,
    children: [
      { path: '/login', element: <LoginPage /> },
      { path: '/signup', element: <SignupPage /> },
    ],
  },
  {
    element: <ProtectedRoute />,
    children: [
      { path: '/dashboard', element: <DashboardPage /> },
      { path: '/session/:sessionId', element: <SessionDetailPage /> },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
])

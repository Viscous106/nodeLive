import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'

export default function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-page px-4 text-center">
      <p className="text-5xl font-bold text-primary">404</p>
      <h1 className="text-xl font-semibold text-text-primary">Page not found</h1>
      <p className="max-w-sm text-sm text-text-muted">
        The page you’re looking for doesn’t exist or may have moved.
      </p>
      <Link to="/dashboard" className="mt-2">
        <Button>Back to dashboard</Button>
      </Link>
    </div>
  )
}

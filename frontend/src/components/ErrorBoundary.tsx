import { Component } from 'react'
import type { ErrorInfo, ReactNode } from 'react'

import { Button } from '@/components/ui/button'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // In production this would go to Sentry (MP milestone).
    console.error('Unhandled UI error:', error, info)
  }

  render() {
    if (!this.state.hasError) return this.props.children
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-page px-4 text-center">
        <h1 className="text-xl font-semibold text-text-primary">
          Something went wrong
        </h1>
        <p className="max-w-sm text-sm text-text-muted">
          An unexpected error occurred. Reloading usually fixes it.
        </p>
        <Button onClick={() => window.location.assign('/dashboard')}>
          Back to dashboard
        </Button>
      </div>
    )
  }
}

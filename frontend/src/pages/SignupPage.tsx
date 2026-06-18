import type { FormEvent } from 'react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { AuthShell } from '@/components/auth/AuthShell'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Spinner } from '@/components/ui/spinner'
import { useSignup } from '@/hooks/useAuth'
import { ApiError } from '@/lib/api'

export default function SignupPage() {
  const navigate = useNavigate()
  const signup = useSignup()
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    signup.mutate(
      { displayName, email, password },
      { onSuccess: () => navigate('/dashboard', { replace: true }) },
    )
  }

  const error = signup.isError
    ? signup.error instanceof ApiError && signup.error.status === 409
      ? 'An account with this email already exists.'
      : 'Could not create your account. Please try again.'
    : null

  return (
    <AuthShell
      title="Create your account"
      subtitle="Join your classes, quizzes, and live sessions."
      footer={
        <>
          Already have an account?{' '}
          <Link to="/login" className="font-semibold text-text-link">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {error && (
          <div
            role="alert"
            className="rounded-btn bg-danger/10 px-3 py-2 text-sm font-medium text-danger"
          >
            {error}
          </div>
        )}
        <div>
          <Label htmlFor="name">Full name</Label>
          <Input
            id="name"
            autoComplete="name"
            required
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Ada Lovelace"
          />
        </div>
        <div>
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@example.com"
          />
        </div>
        <div>
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="At least 8 characters"
          />
        </div>
        <Button
          type="submit"
          className="w-full"
          size="lg"
          disabled={signup.isPending}
        >
          {signup.isPending && <Spinner />}
          Create account
        </Button>
      </form>
    </AuthShell>
  )
}

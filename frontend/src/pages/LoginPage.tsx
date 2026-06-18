import type { FormEvent } from 'react'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { AuthShell } from '@/components/auth/AuthShell'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Spinner } from '@/components/ui/spinner'
import { useLogin } from '@/hooks/useAuth'
import { ApiError } from '@/lib/api'

export default function LoginPage() {
  const navigate = useNavigate()
  const login = useLogin()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    login.mutate(
      { email, password },
      { onSuccess: () => navigate('/dashboard', { replace: true }) },
    )
  }

  const error = login.isError
    ? login.error instanceof ApiError && login.error.status === 401
      ? 'Incorrect email or password.'
      : 'Could not sign in. Please try again.'
    : null

  return (
    <AuthShell
      title="Welcome back"
      subtitle="Sign in to continue to your classes."
      footer={
        <>
          New here?{' '}
          <Link to="/signup" className="font-semibold text-text-link">
            Create an account
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
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Your password"
          />
        </div>
        <Button
          type="submit"
          className="w-full"
          size="lg"
          disabled={login.isPending}
        >
          {login.isPending && <Spinner />}
          Sign in
        </Button>
      </form>
    </AuthShell>
  )
}

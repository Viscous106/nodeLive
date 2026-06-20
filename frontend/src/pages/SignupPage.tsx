import type { FormEvent } from 'react'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { AuthShell } from '@/components/auth/AuthShell'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Spinner } from '@/components/ui/spinner'
import { useInvitePreview } from '@/hooks/useAdmin'
import { useSignup } from '@/hooks/useAuth'
import { ApiError } from '@/lib/api'

export default function SignupPage() {
  const navigate = useNavigate()
  const signup = useSignup()
  const [params] = useSearchParams()
  const inviteToken = params.get('invite')
  const preview = useInvitePreview(inviteToken)
  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  // An accepted invite is email-locked — pin the field to the invited address.
  useEffect(() => {
    if (preview.data?.email) setEmail(preview.data.email)
  }, [preview.data?.email])

  const invited = Boolean(inviteToken && preview.data)

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    signup.mutate(
      { displayName, email, password, inviteToken: inviteToken ?? undefined },
      { onSuccess: () => navigate('/dashboard', { replace: true }) },
    )
  }

  const error = signup.isError
    ? signup.error instanceof ApiError && signup.error.status === 409
      ? 'An account with this email already exists.'
      : signup.error instanceof ApiError && signup.error.status === 400
        ? 'This invitation is invalid, expired, or for a different email.'
        : 'Could not create your account. Please try again.'
    : null

  const role = preview.data?.role
  const roleLabel = role ? role[0] + role.slice(1).toLowerCase() : ''

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
        {invited && (
          <div className="rounded-btn bg-primary/10 px-3 py-2 text-sm font-medium text-primary">
            You're joining <strong>{preview.data?.orgName}</strong> as{' '}
            <strong>{roleLabel}</strong>.
          </div>
        )}
        {inviteToken && preview.isError && (
          <div
            role="alert"
            className="rounded-btn bg-danger/10 px-3 py-2 text-sm font-medium text-danger"
          >
            This invitation link is invalid or has expired.
          </div>
        )}
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
            readOnly={invited}
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

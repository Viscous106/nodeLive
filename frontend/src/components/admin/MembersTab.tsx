import { Copy, Trash2, UserPlus } from 'lucide-react'
import type { FormEvent } from 'react'
import { useState } from 'react'

import { Avatar } from '@/components/ui/avatar'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Spinner } from '@/components/ui/spinner'
import {
  useCreateInvitation,
  useInvitations,
  useMembers,
  useRevokeInvitation,
  useSetRole,
} from '@/hooks/useAdmin'
import { toast } from '@/stores/toastStore'
import type { Member, UserRole } from '@/types'

const ROLES: UserRole[] = ['STUDENT', 'INSTRUCTOR', 'ADMIN']

const ROLE_BADGE: Record<UserRole, 'default' | 'new' | 'success'> = {
  STUDENT: 'default',
  INSTRUCTOR: 'new',
  ADMIN: 'success',
}

function titleCase(s: string) {
  return s[0] + s.slice(1).toLowerCase()
}

export function MembersTab() {
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_360px]">
      <MembersCard />
      <InvitationsCard />
    </div>
  )
}

function MembersCard() {
  const { data: members, isLoading } = useMembers()
  const setRole = useSetRole()

  return (
    <Card>
      <CardHeader className="flex items-center justify-between">
        <CardTitle>Members &amp; roles</CardTitle>
        {members && (
          <span className="text-sm text-text-muted">{members.length} members</span>
        )}
      </CardHeader>
      <CardContent className="space-y-1">
        {isLoading && (
          <div className="space-y-3 pt-1">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        )}
        {members?.length === 0 && (
          <p className="py-6 text-center text-sm text-text-muted">No members yet.</p>
        )}
        {members?.map((m) => (
          <MemberRow
            key={m.userId}
            member={m}
            disabled={setRole.isPending}
            onRoleChange={(role) => setRole.mutate({ userId: m.userId, role })}
          />
        ))}
      </CardContent>
    </Card>
  )
}

function MemberRow({
  member,
  disabled,
  onRoleChange,
}: {
  member: Member
  disabled: boolean
  onRoleChange: (role: UserRole) => void
}) {
  return (
    <div className="flex items-center gap-3 rounded-lg px-2 py-2 hover:bg-border-muted/50">
      <Avatar name={member.displayName} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-text-primary">
          {member.displayName}
        </p>
        <p className="truncate text-xs text-text-muted">{member.email}</p>
      </div>
      <Badge variant={ROLE_BADGE[member.role]} className="hidden sm:inline-flex">
        {member.role}
      </Badge>
      <label className="sr-only" htmlFor={`role-${member.userId}`}>
        Role for {member.displayName}
      </label>
      <select
        id={`role-${member.userId}`}
        value={member.role}
        disabled={disabled}
        onChange={(e) => onRoleChange(e.target.value as UserRole)}
        className="h-9 rounded-btn border border-border bg-card px-2 text-sm font-medium text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 disabled:opacity-50"
      >
        {ROLES.map((r) => (
          <option key={r} value={r}>
            {titleCase(r)}
          </option>
        ))}
      </select>
    </div>
  )
}

function InvitationsCard() {
  const { data: invites, isLoading } = useInvitations()
  const create = useCreateInvitation()
  const revoke = useRevokeInvitation()
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<UserRole>('INSTRUCTOR')

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    create.mutate({ email, role }, { onSuccess: () => setEmail('') })
  }

  function copyLink(inviteUrl: string) {
    void navigator.clipboard
      .writeText(window.location.origin + inviteUrl)
      .then(() => toast({ variant: 'success', title: 'Invite link copied' }))
  }

  return (
    <Card className="self-start">
      <CardHeader>
        <CardTitle>Invite by link</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <form onSubmit={onSubmit} className="space-y-3" noValidate>
          <div>
            <Label htmlFor="invite-email">Email</Label>
            <Input
              id="invite-email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="prof@university.edu"
            />
          </div>
          <div>
            <Label htmlFor="invite-role">Role</Label>
            <select
              id="invite-role"
              value={role}
              onChange={(e) => setRole(e.target.value as UserRole)}
              className="h-10 w-full rounded-btn border border-border bg-card px-3 text-sm text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {titleCase(r)}
                </option>
              ))}
            </select>
          </div>
          <Button type="submit" className="w-full" disabled={create.isPending}>
            {create.isPending ? <Spinner /> : <UserPlus className="h-4 w-4" />}
            Create invite
          </Button>
        </form>

        <div className="space-y-2 border-t border-border pt-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-text-muted">
            Pending invitations
          </p>
          {isLoading && <Skeleton className="h-10 w-full" />}
          {invites?.length === 0 && (
            <p className="py-2 text-sm text-text-muted">No pending invitations.</p>
          )}
          {invites?.map((inv) => (
            <div
              key={inv.id}
              className="flex items-center gap-2 rounded-lg border border-border px-2 py-2"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-text-primary">
                  {inv.email}
                </p>
                <p className="text-xs text-text-muted">{inv.role}</p>
              </div>
              <button
                type="button"
                onClick={() => copyLink(inv.inviteUrl)}
                aria-label={`Copy invite link for ${inv.email}`}
                className="rounded-btn p-2 text-text-secondary hover:bg-border-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40"
              >
                <Copy className="h-4 w-4" />
              </button>
              <button
                type="button"
                onClick={() => revoke.mutate(inv.id)}
                disabled={revoke.isPending}
                aria-label={`Revoke invitation for ${inv.email}`}
                className="rounded-btn p-2 text-danger hover:bg-danger/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/40 disabled:opacity-50"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}

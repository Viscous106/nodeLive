import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { ApiError, api } from '@/lib/api'
import { toast } from '@/stores/toastStore'
import type { Invitation, InvitePreview, Member, UserRole } from '@/types'

const MEMBERS_KEY = ['admin', 'members'] as const
const INVITES_KEY = ['admin', 'invitations'] as const

export function useMembers() {
  return useQuery({
    queryKey: MEMBERS_KEY,
    queryFn: () => api.get<Member[]>('/api/admin/members'),
  })
}

export function useSetRole() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ userId, role }: { userId: string; role: UserRole }) =>
      api.patch<Member>(`/api/admin/members/${userId}/role`, { role }),
    onSuccess: (m) => {
      qc.invalidateQueries({ queryKey: MEMBERS_KEY })
      toast({ variant: 'success', title: `${m.displayName} is now ${m.role}` })
    },
    onError: (e) =>
      toast({
        variant: 'error',
        title:
          e instanceof ApiError && e.status === 409
            ? 'An org must keep at least one admin.'
            : 'Could not update the role.',
      }),
  })
}

export function useInvitations() {
  return useQuery({
    queryKey: INVITES_KEY,
    queryFn: () => api.get<Invitation[]>('/api/admin/invitations'),
  })
}

export function useCreateInvitation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (input: { email: string; role: UserRole }) =>
      api.post<Invitation>('/api/admin/invitations', input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: INVITES_KEY })
      toast({ variant: 'success', title: 'Invitation created' })
    },
    onError: (e) =>
      toast({
        variant: 'error',
        title:
          e instanceof ApiError && e.status === 409
            ? 'That email already belongs to a member.'
            : 'Could not create the invitation.',
      }),
  })
}

export function useRevokeInvitation() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api.delete<null>(`/api/admin/invitations/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: INVITES_KEY }),
  })
}

/** Public invite preview (signup screen) — no auth. */
export function useInvitePreview(token: string | null) {
  return useQuery({
    queryKey: ['invite', token],
    queryFn: () => api.get<InvitePreview>(`/api/invitations/${token}`),
    enabled: Boolean(token),
    retry: false,
    staleTime: Infinity,
  })
}

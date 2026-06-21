import { useEffect, useState } from 'react'

import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Avatar } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { useAuth, useUpdateProfile } from '@/hooks/useAuth'

export default function SettingsPage() {
  const { user } = useAuth()
  const update = useUpdateProfile()

  const [displayName, setDisplayName] = useState(user?.displayName ?? '')
  const [avatarUrl, setAvatarUrl] = useState(user?.avatarUrl ?? '')

  // Sync if user loads after mount
  useEffect(() => {
    if (user) {
      setDisplayName(user.displayName)
      setAvatarUrl(user.avatarUrl ?? '')
    }
  }, [user])

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const patch: { displayName?: string; avatarUrl?: string } = {}
    if (displayName.trim() !== (user?.displayName ?? '')) {
      patch.displayName = displayName.trim()
    }
    if (avatarUrl.trim() !== (user?.avatarUrl ?? '')) {
      patch.avatarUrl = avatarUrl.trim() || undefined
    }
    if (Object.keys(patch).length === 0) return
    update.mutate(patch)
  }

  return (
    <DashboardLayout>
      <div className="space-y-1">
        <h1 className="text-2xl font-bold text-text-primary">Settings</h1>
        <p className="text-sm text-text-secondary">Update your profile information.</p>
      </div>

      <div className="mt-6 max-w-lg">
        <Card>
          <CardHeader>
            <CardTitle>Profile</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="mb-6 flex items-center gap-4">
              <Avatar
                name={displayName || (user?.displayName ?? '')}
                src={avatarUrl || null}
                className="h-16 w-16 text-xl"
              />
              <div>
                <p className="text-sm font-medium text-text-primary">
                  {user?.displayName}
                </p>
                <p className="text-xs text-text-muted">{user?.email}</p>
              </div>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div className="space-y-1.5">
                <label
                  htmlFor="displayName"
                  className="text-sm font-medium text-text-primary"
                >
                  Display name
                </label>
                <Input
                  id="displayName"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="Your name"
                  required
                />
              </div>

              <div className="space-y-1.5">
                <label
                  htmlFor="avatarUrl"
                  className="text-sm font-medium text-text-primary"
                >
                  Avatar URL
                  <span className="ml-1 text-text-muted">(optional)</span>
                </label>
                <Input
                  id="avatarUrl"
                  type="url"
                  value={avatarUrl}
                  onChange={(e) => setAvatarUrl(e.target.value)}
                  placeholder="https://example.com/avatar.png"
                />
              </div>

              <Button
                type="submit"
                disabled={update.isPending || !displayName.trim()}
                className="w-full"
              >
                {update.isPending ? 'Saving…' : 'Save changes'}
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  )
}

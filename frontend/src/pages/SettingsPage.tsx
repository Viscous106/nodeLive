import { useEffect, useState } from 'react'

import { DashboardLayout } from '@/components/layout/DashboardLayout'
import { Avatar } from '@/components/ui/avatar'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { useAuth, useUpdateProfile } from '@/hooks/useAuth'

export default function SettingsPage() {
  const { user } = useAuth()
  const update = useUpdateProfile()

  const [displayName, setDisplayName] = useState(user?.displayName ?? '')
  const [avatarUrl, setAvatarUrl] = useState(user?.avatarUrl ?? '')

  useEffect(() => {
    if (user) {
      setDisplayName(user.displayName)
      setAvatarUrl(user.avatarUrl ?? '')
    }
  }, [user])

  function handleSave(e: React.FormEvent) {
    e.preventDefault()
    update.mutate({
      displayName: displayName.trim() || undefined,
      avatarUrl: avatarUrl.trim() || undefined,
    })
  }

  const dirty =
    displayName.trim() !== (user?.displayName ?? '') ||
    (avatarUrl.trim() || null) !== (user?.avatarUrl ?? null)

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Settings</h1>
          <p className="mt-1 text-sm text-text-muted">Manage your profile.</p>
        </div>

        <Card className="max-w-lg">
          <CardHeader>
            <CardTitle>Profile</CardTitle>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSave} className="space-y-5">
              <div className="flex items-center gap-4">
                <Avatar
                  name={displayName || user?.displayName || '?'}
                  src={avatarUrl || null}
                  className="h-16 w-16 text-xl"
                />
                <div className="flex-1 space-y-1">
                  <Label htmlFor="avatar-url">Avatar URL</Label>
                  <Input
                    id="avatar-url"
                    type="url"
                    value={avatarUrl}
                    onChange={(e) => setAvatarUrl(e.target.value)}
                    placeholder="https://example.com/avatar.jpg"
                  />
                </div>
              </div>

              <div className="space-y-1">
                <Label htmlFor="display-name">Display name</Label>
                <Input
                  id="display-name"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="Your name"
                />
              </div>

              <div className="space-y-1">
                <Label>Email</Label>
                <Input value={user?.email ?? ''} disabled />
              </div>

              <Button
                type="submit"
                disabled={!dirty || !displayName.trim() || update.isPending}
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

import { ExternalLink, FileText } from 'lucide-react'
import { useState } from 'react'

import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Skeleton } from '@/components/ui/skeleton'
import { Spinner } from '@/components/ui/spinner'
import { useAuth } from '@/hooks/useAuth'
import { useCreateNote, useNotes } from '@/hooks/useNotes'
import type { ClassSession, LectureNote, NoteKind } from '@/types'

const KINDS: NoteKind[] = ['LINK', 'PDF', 'SLIDES', 'SUMMARY']

function NoteRow({ note }: { note: LectureNote }) {
  return (
    <div className="flex items-center gap-3 rounded-card border border-border bg-card p-4">
      <FileText className="h-5 w-5 shrink-0 text-primary" />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-text-primary">
          {note.title}
        </p>
        <Badge variant="default" className="mt-1">
          {note.kind}
        </Badge>
      </div>
      <a
        href={note.url}
        target="_blank"
        rel="noreferrer"
        className="flex items-center gap-1.5 text-sm font-medium text-text-link"
      >
        Open
        <ExternalLink className="h-4 w-4" />
      </a>
    </div>
  )
}

function AddNoteForm({ sessionId }: { sessionId: string }) {
  const create = useCreateNote(sessionId)
  const [open, setOpen] = useState(false)
  const [title, setTitle] = useState('')
  const [url, setUrl] = useState('')
  const [kind, setKind] = useState<NoteKind>('LINK')

  if (!open) {
    return (
      <Button variant="outline" onClick={() => setOpen(true)}>
        + Add material
      </Button>
    )
  }

  return (
    <Card>
      <CardContent className="space-y-3 pt-4">
        <div>
          <Label htmlFor="note-title">Title</Label>
          <Input
            id="note-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Isolation Levels — slides"
          />
        </div>
        <div>
          <Label htmlFor="note-url">Link</Label>
          <Input
            id="note-url"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="https://…"
          />
        </div>
        <div>
          <Label htmlFor="note-kind">Type</Label>
          <select
            id="note-kind"
            value={kind}
            onChange={(e) => setKind(e.target.value as NoteKind)}
            className="h-10 w-full rounded-btn border border-border bg-card px-3 text-sm text-text-primary focus-visible:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/30"
          >
            {KINDS.map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </div>
        <div className="flex gap-2">
          <Button
            disabled={!title.trim() || !url.trim() || create.isPending}
            onClick={() =>
              create.mutate(
                { title, url, kind },
                {
                  onSuccess: () => {
                    setTitle('')
                    setUrl('')
                    setKind('LINK')
                    setOpen(false)
                  },
                },
              )
            }
          >
            {create.isPending && <Spinner />}
            Add
          </Button>
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

export function NotesTab({ session }: { session: ClassSession }) {
  const { user } = useAuth()
  const isStaff =
    !!user &&
    (user.role === 'INSTRUCTOR' ||
      user.role === 'ADMIN' ||
      user.id === session.hostId)
  const { data, isLoading } = useNotes(session.id)

  return (
    <div className="space-y-4">
      {isStaff && <AddNoteForm sessionId={session.id} />}

      {isLoading ? (
        <Skeleton className="h-24" />
      ) : data && data.length > 0 ? (
        <div className="space-y-2">
          {data.map((n) => (
            <NoteRow key={n.id} note={n} />
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center gap-2 rounded-card border border-border bg-card py-10 text-center">
          <FileText className="h-8 w-8 text-text-muted" />
          <p className="text-sm text-text-muted">No materials posted yet.</p>
        </div>
      )}
    </div>
  )
}

import { AlertCircle, Video } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Spinner } from '@/components/ui/spinner'
import type { ZoomStatus } from '@/hooks/useZoomSDK'

interface Props {
  rootRef: React.RefObject<HTMLDivElement | null>
  status: ZoomStatus
  errorMsg: string
  onJoin: () => void
  hasZoomMeeting?: boolean
}

/**
 * Hosts the Zoom Component View. The SDK renders into `rootRef`; an overlay
 * covers it until the user is in the meeting. A join failure (e.g. no real Zoom
 * creds locally) shows an error with retry -- the rest of the page still works,
 * since the feature panel is socket-driven and independent of the video.
 *
 * When `hasZoomMeeting` is false an info state is shown instead of the join
 * button -- it is not an error, so there is no retry.
 */
export function ZoomPanel({ rootRef, status, errorMsg, onJoin, hasZoomMeeting = true }: Props) {
  return (
    <div className="relative flex-1 bg-black">
      <div ref={rootRef} id="zoomAppRoot" className="h-full w-full" />

      {status !== 'in-meeting' && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-4 bg-black p-6 text-center text-white">
          {!hasZoomMeeting ? (
            <div className="flex max-w-md flex-col items-center gap-3">
              <Video size={36} className="text-white/50" />
              <p className="text-sm text-white/70">
                No Zoom meeting has been configured for this session yet.
              </p>
            </div>
          ) : status === 'joining' ? (
            <>
              <Spinner />
              <p className="text-sm text-white/70">Joining the meeting...</p>
            </>
          ) : status === 'error' ? (
            <div className="flex max-w-md flex-col items-center gap-3">
              <AlertCircle className="text-red-500" size={32} />
              <p className="text-sm font-medium">Couldn't join the Zoom meeting</p>
              <p className="text-xs break-words text-white/60">{errorMsg}</p>
              <Button variant="outline" size="sm" onClick={onJoin}>
                Try again
              </Button>
            </div>
          ) : (
            <>
              <Video size={36} className="text-white/70" />
              <p className="text-sm text-white/70">
                Ready to join the live video.
              </p>
              <Button onClick={onJoin}>Join video</Button>
            </>
          )}
        </div>
      )}
    </div>
  )
}

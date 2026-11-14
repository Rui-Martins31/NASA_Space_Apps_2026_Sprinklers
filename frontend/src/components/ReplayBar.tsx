import { useEffect, useMemo } from 'react'
import { Slider } from '@base-ui/react/slider'
import { Pause, Play, X } from '@phosphor-icons/react'
import { useApp } from '../store'

const REPLAY_SECONDS = 25 // the whole period plays in about this long

function fmtDate(ts: number) {
  return new Date(ts).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'UTC' })
}

// Timeline at the bottom of the screen while a replay is active.
export default function ReplayBar() {
  const replayTime = useApp((s) => s.replayTime)
  const playing = useApp((s) => s.replayPlaying)
  const hotspots = useApp((s) => s.hotspots)
  const dateFrom = useApp((s) => s.dateFrom)
  const dateTo = useApp((s) => s.dateTo)
  const setReplay = useApp((s) => s.setReplay)

  const start = new Date(dateFrom).getTime()
  const end = new Date(dateTo).getTime() + 86_399_000

  // How many hotspots have appeared so far (for the counter)
  const sortedTs = useMemo(
    () =>
      (hotspots ?? [])
        .map((h) => new Date(h.date_time.endsWith('Z') ? h.date_time : `${h.date_time}Z`).getTime())
        .sort((a, b) => a - b),
    [hotspots],
  )
  const shown = useMemo(() => {
    if (replayTime === null) return 0
    let lo = 0,
      hi = sortedTs.length
    while (lo < hi) {
      const mid = (lo + hi) >> 1
      if (sortedTs[mid] <= replayTime) lo = mid + 1
      else hi = mid
    }
    return lo
  }, [sortedTs, replayTime])

  // Playback loop
  useEffect(() => {
    if (!playing) return
    let frame = 0
    let last = performance.now()
    const step = (now: number) => {
      const t = useApp.getState().replayTime ?? start
      const next = t + ((end - start) / (REPLAY_SECONDS * 1000)) * (now - last)
      last = now
      if (next >= end) {
        setReplay(end, false)
        return
      }
      setReplay(next, true)
      frame = requestAnimationFrame(step)
    }
    frame = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame)
  }, [playing, start, end, setReplay])

  // Space bar toggles play/pause
  useEffect(() => {
    if (replayTime === null) return
    const onKey = (e: KeyboardEvent) => {
      if (e.code !== 'Space' || (e.target as HTMLElement).closest('input, textarea, button')) return
      e.preventDefault()
      const s = useApp.getState()
      if (s.replayTime !== null && s.replayTime >= end) s.setReplay(start, true)
      else s.setReplay(s.replayTime, !s.replayPlaying)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [replayTime === null, start, end]) // eslint-disable-line react-hooks/exhaustive-deps

  if (replayTime === null) return null

  const togglePlay = () => {
    if (replayTime >= end) setReplay(start, true)
    else setReplay(replayTime, !playing)
  }

  return (
    <div className="glass absolute bottom-6 left-1/2 z-20 flex w-[min(640px,calc(100vw-32px))] -translate-x-1/2 items-center gap-4 rounded-[14px] px-4 py-3 animate-[panel-in_240ms_cubic-bezier(0.23,1,0.32,1)]">
      <button
        onClick={togglePlay}
        aria-label={playing ? 'Pause replay' : 'Play replay'}
        className="grid size-10 shrink-0 place-items-center rounded-full bg-ember-500 text-ink-950 transition-transform duration-150 active:scale-95"
      >
        {playing ? <Pause size={18} weight="fill" /> : <Play size={18} weight="fill" />}
      </button>

      <div className="min-w-0 flex-1">
        <div className="mb-1.5 flex items-baseline justify-between gap-3">
          <span className="font-mono text-[15px] text-fg">{fmtDate(replayTime)}</span>
          <span className="font-mono text-[11px] text-fg-muted">
            {shown.toLocaleString('en')} / {sortedTs.length.toLocaleString('en')} hotspots
          </span>
        </div>
        <Slider.Root
          value={replayTime}
          min={start}
          max={end}
          step={3_600_000}
          onValueChange={(v) => setReplay(v as number, false)}
        >
          <Slider.Control className="flex h-4 w-full touch-none items-center select-none">
            <Slider.Track className="h-1 w-full rounded-full bg-ink-700">
              <Slider.Indicator className="rounded-full bg-ember-500" />
              <Slider.Thumb aria-label="Replay date" className="size-3.5 rounded-full bg-fg outline-none focus-visible:shadow-[0_0_0_4px_rgb(255_107_26/0.45)]" />
            </Slider.Track>
          </Slider.Control>
        </Slider.Root>
        <div className="mt-1 flex justify-between font-mono text-[10px] text-fg-muted">
          <span>{fmtDate(start)}</span>
          <span>{fmtDate(end)}</span>
        </div>
      </div>

      <button
        onClick={() => setReplay(null, false)}
        aria-label="Stop replay and show all hotspots"
        className="shrink-0 rounded-md p-1.5 text-fg-muted hover:bg-ink-700 hover:text-fg"
      >
        <X size={18} />
      </button>
    </div>
  )
}

import { useEffect, useRef, useState } from 'react'
import { Command } from 'cmdk'
import { MagnifyingGlass, MapPin, X, Crosshair } from '@phosphor-icons/react'
import clsx from 'clsx'
import { searchPlaces } from '../api/geocode'
import { useApp } from '../store'
import type { Place } from '../types'

// Place search as a command palette (cmdk). Ctrl/Cmd + K focuses it from anywhere.
export default function SearchBar() {
  const place = useApp((s) => s.place)
  const setPlace = useApp((s) => s.setPlace)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<Place[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  // Ctrl/Cmd + K shortcut
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        inputRef.current?.focus()
        inputRef.current?.select()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  // Search while typing, 250 ms after the last key press
  useEffect(() => {
    if (!open) return
    const ctrl = new AbortController()
    const t = setTimeout(async () => {
      if (query.trim().length < 2) {
        setResults([])
        return
      }
      setLoading(true)
      setError(null)
      try {
        setResults(await searchPlaces(query, ctrl.signal))
      } catch (e) {
        if ((e as Error).name !== 'AbortError') setError((e as Error).message)
      } finally {
        setLoading(false)
      }
    }, 250)
    return () => {
      clearTimeout(t)
      ctrl.abort()
    }
  }, [query, open])

  function choose(p: Place) {
    setPlace(p)
    setQuery(p.detail ? `${p.label}, ${p.detail}` : p.label)
    setOpen(false)
    inputRef.current?.blur()
  }

  function clear() {
    setQuery('')
    setResults([])
    setPlace(null)
    inputRef.current?.focus()
  }

  const showList = open && query.trim().length >= 2

  return (
    <Command shouldFilter={false} label="Search a place" className="relative w-full">
      <div className="glass flex h-12 items-center gap-2.5 rounded-[14px] px-4">
        <MagnifyingGlass size={18} className="shrink-0 text-fg-muted" />
        <Command.Input
          ref={inputRef}
          value={query}
          onValueChange={(v) => {
            setQuery(v)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 120)}
          placeholder="Search a place or type lat, lon"
          className="h-full min-w-0 flex-1 bg-transparent text-[15px] text-fg outline-none placeholder:text-fg-muted"
        />
        {query || place ? (
          <button onClick={clear} aria-label="Clear search" className="rounded-md p-1 text-fg-muted hover:bg-ink-700 hover:text-fg">
            <X size={16} />
          </button>
        ) : (
          <kbd className="rounded-md border border-line px-1.5 py-0.5 font-mono text-[11px] text-fg-muted">Ctrl K</kbd>
        )}
      </div>

      {showList && (
        <Command.List className="glass absolute top-14 z-30 w-full overflow-hidden rounded-[14px] p-1.5">
          {loading && <Command.Loading><div className="px-3 py-2.5 text-sm text-fg-muted">Searching…</div></Command.Loading>}
          {error && <div className="px-3 py-2.5 text-sm text-ember-300">{error}</div>}
          {!loading && !error && <Command.Empty className="px-3 py-2.5 text-sm text-fg-muted">No places found.</Command.Empty>}
          {results.map((p, i) => (
            <Command.Item
              key={`${p.lat},${p.lon},${i}`}
              value={`${p.label}-${i}`}
              onSelect={() => choose(p)}
              onMouseDown={(e) => e.preventDefault()}
              className={clsx('flex cursor-pointer items-center gap-3 rounded-[10px] px-3 py-2.5')}
            >
              {!p.detail ? (
                <Crosshair size={18} className="shrink-0 text-ember-300" />
              ) : (
                <MapPin size={18} className="shrink-0 text-fg-muted" />
              )}
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm text-fg">{p.label}</div>
                <div className="truncate text-xs text-fg-muted">{p.detail || 'Coordinates'}</div>
              </div>
              <span className="shrink-0 font-mono text-[11px] text-fg-muted">
                {p.lat.toFixed(2)}, {p.lon.toFixed(2)}
              </span>
            </Command.Item>
          ))}
        </Command.List>
      )}
    </Command>
  )
}

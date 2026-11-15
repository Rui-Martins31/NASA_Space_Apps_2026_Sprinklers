import { useState } from 'react'
import { Popover } from '@base-ui/react/popover'
import { CalendarBlank, CaretLeft, CaretRight } from '@phosphor-icons/react'
import clsx from 'clsx'
import { monthName, useT, type Lang } from '../i18n'
import { useApp } from '../store'

// Date picker styled like the rest of the app (replaces the browser's own
// calendar pop-up, which looks different on every system).
// Values are 'YYYY-MM-DD' strings, like everywhere else in the app.

const WEEKDAYS: Record<Lang, string[]> = {
  en: ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'],
  pt: ['Se', 'Te', 'Qu', 'Qu', 'Se', 'Sá', 'Do'],
}

const TODAY = new Date().toISOString().slice(0, 10)
const pad = (n: number) => String(n).padStart(2, '0')
const iso = (y: number, m: number, d: number) => `${y}-${pad(m + 1)}-${pad(d)}`
function parse(s: string) {
  const [y, m, d] = s.split('-').map(Number)
  return { y, m: m - 1, d }
}
function display(s: string, lang: Lang) {
  const { y, m, d } = parse(s)
  return `${pad(d)} ${monthName(m + 1, lang)} ${y}`
}

interface Props {
  label: string
  value: string
  min: string
  max: string
  onChange: (v: string) => void
}

export default function DatePicker({ label, value, min, max, onChange }: Props) {
  const t = useT()
  const lang = useApp((s) => s.lang)
  const [open, setOpen] = useState(false)
  const [view, setView] = useState(() => {
    const { y, m } = parse(value)
    return { y, m }
  })

  const minP = parse(min)
  const maxP = parse(max)
  const years = Array.from({ length: maxP.y - minP.y + 1 }, (_, i) => maxP.y - i)

  const daysInMonth = new Date(view.y, view.m + 1, 0).getDate()
  const firstWeekday = (new Date(view.y, view.m, 1).getDay() + 6) % 7 // Monday = 0
  const cells: (number | null)[] = [...Array(firstWeekday).fill(null), ...Array.from({ length: daysInMonth }, (_, i) => i + 1)]

  const canPrev = view.y > minP.y || (view.y === minP.y && view.m > minP.m)
  const canNext = view.y < maxP.y || (view.y === maxP.y && view.m < maxP.m)
  const shift = (delta: number) =>
    setView((v) => {
      const m = v.m + delta
      return { y: v.y + Math.floor(m / 12), m: ((m % 12) + 12) % 12 }
    })

  return (
    <Popover.Root
      open={open}
      onOpenChange={(o) => {
        setOpen(o)
        if (o) setView(parse(value)) // reopen on the selected month
      }}
    >
      <Popover.Trigger className="block w-full rounded-[10px] bg-ink-800 px-3 py-2 text-left ring-1 ring-line transition-shadow duration-150 hover:ring-fg/20 data-[popup-open]:ring-ember-500/60">
        <span className="block text-[10px] uppercase tracking-[0.08em] text-fg-muted">{label}</span>
        <span className="flex items-center justify-between font-mono text-[13px] text-fg">
          {display(value, lang)}
          <CalendarBlank size={14} className="text-fg-muted" />
        </span>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Positioner side="bottom" align="start" sideOffset={6} className="z-40">
          <Popover.Popup className="popover-popup glass w-[288px] rounded-[14px] p-3 outline-none">
            {/* Month / year navigation */}
            <div className="mb-2 flex items-center gap-1">
              <button
                onClick={() => shift(-1)}
                disabled={!canPrev}
                aria-label={t('date.prev')}
                className="grid size-8 place-items-center rounded-[8px] text-fg-muted hover:bg-ink-700 hover:text-fg disabled:opacity-30"
              >
                <CaretLeft size={16} />
              </button>
              <select
                value={view.m}
                onChange={(e) => setView((v) => ({ ...v, m: Number(e.target.value) }))}
                aria-label={t('date.month')}
                className="h-8 flex-1 cursor-pointer appearance-none rounded-[8px] bg-transparent px-2 text-center font-display text-sm font-semibold text-fg outline-none hover:bg-ink-700 focus-visible:ring-1 focus-visible:ring-ember-500/60"
              >
                {Array.from({ length: 12 }, (_, i) => monthName(i + 1, lang, 'long')).map((name, i) => (
                  <option key={name} value={i} className="bg-ink-900">
                    {name}
                  </option>
                ))}
              </select>
              <select
                value={view.y}
                onChange={(e) => setView((v) => ({ ...v, y: Number(e.target.value) }))}
                aria-label={t('date.year')}
                className="h-8 cursor-pointer appearance-none rounded-[8px] bg-transparent px-2 text-center font-mono text-sm text-fg outline-none hover:bg-ink-700 focus-visible:ring-1 focus-visible:ring-ember-500/60"
              >
                {years.map((y) => (
                  <option key={y} value={y} className="bg-ink-900">
                    {y}
                  </option>
                ))}
              </select>
              <button
                onClick={() => shift(1)}
                disabled={!canNext}
                aria-label={t('date.next')}
                className="grid size-8 place-items-center rounded-[8px] text-fg-muted hover:bg-ink-700 hover:text-fg disabled:opacity-30"
              >
                <CaretRight size={16} />
              </button>
            </div>

            {/* Day grid */}
            <div className="grid grid-cols-7 gap-0.5 text-center">
              {WEEKDAYS[lang].map((w, wi) => (
                <div key={wi} className="pb-1 text-[10.5px] text-fg-muted">
                  {w}
                </div>
              ))}
              {cells.map((d, i) => {
                if (d === null) return <div key={`e${i}`} />
                const v = iso(view.y, view.m, d)
                const selected = v === value
                const disabled = v < min || v > max
                const isToday = v === TODAY
                return (
                  <button
                    key={v}
                    disabled={disabled}
                    onClick={() => {
                      onChange(v)
                      setOpen(false)
                    }}
                    aria-label={display(v, lang)}
                    aria-pressed={selected}
                    className={clsx(
                      'h-8 rounded-[8px] font-mono text-[12.5px] transition-colors duration-100 outline-none focus-visible:ring-1 focus-visible:ring-ember-500/70',
                      selected ? 'bg-ember-500 font-medium text-ink-950' : 'text-fg hover:bg-ink-700',
                      isToday && !selected && 'ring-1 ring-ember-500/40',
                      disabled && 'pointer-events-none opacity-25',
                    )}
                  >
                    {d}
                  </button>
                )
              })}
            </div>

            <div className="mt-2 flex justify-between border-t border-line pt-2">
              <button
                onClick={() => {
                  onChange(min)
                  setOpen(false)
                }}
                className="rounded-[6px] px-2 py-1 text-xs text-fg-muted hover:bg-ink-700 hover:text-fg"
              >
                {t('date.earliest')}
              </button>
              <button
                onClick={() => {
                  onChange(max)
                  setOpen(false)
                }}
                className="rounded-[6px] px-2 py-1 text-xs text-ember-300 hover:bg-ink-700"
              >
                {t('date.latest')}
              </button>
            </div>
          </Popover.Popup>
        </Popover.Positioner>
      </Popover.Portal>
    </Popover.Root>
  )
}

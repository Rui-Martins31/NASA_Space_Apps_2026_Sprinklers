import { Cube, GlobeHemisphereWest, Mountains } from '@phosphor-icons/react'
import clsx from 'clsx'
import type { ReactNode } from 'react'
import { useApp } from '../store'
import { useT } from '../i18n'

function Btn({ active, onClick, label, children }: { active: boolean; onClick: () => void; label: string; children: ReactNode }) {
  return (
    <button
      onClick={onClick}
      aria-pressed={active}
      title={label}
      className={clsx(
        'flex h-8 items-center gap-1.5 rounded-[8px] px-2.5 text-xs transition-colors duration-150',
        active ? 'bg-ember-500/15 text-ember-300' : 'text-fg-muted hover:bg-ink-700 hover:text-fg',
      )}
    >
      {children}
    </button>
  )
}

// Bottom-left switches: basemap (dark / satellite) and 3D terrain.
export default function MapModeToggle() {
  const t = useT()
  const basemap = useApp((s) => s.basemap)
  const terrain3d = useApp((s) => s.terrain3d)
  const { setBasemap, setTerrain3d } = useApp.getState()

  return (
    <div className="glass absolute bottom-2.5 left-[52px] z-10 flex items-center gap-1 rounded-[10px] p-1">
      <Btn active={basemap === 'dark'} onClick={() => setBasemap('dark')} label={t('map.darkTitle')}>
        <GlobeHemisphereWest size={16} /> {t('map.dark')}
      </Btn>
      <Btn active={basemap === 'satellite'} onClick={() => setBasemap('satellite')} label={t('map.satTitle')}>
        <Mountains size={16} /> {t('map.satellite')}
      </Btn>
      <span className="mx-0.5 h-5 w-px bg-line" />
      <Btn active={terrain3d} onClick={() => setTerrain3d(!terrain3d)} label={t('map.3dTitle')}>
        <Cube size={16} /> {t('map.3d')}
      </Btn>
    </div>
  )
}

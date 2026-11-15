import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import '@fontsource/space-grotesk/500.css'
import '@fontsource/space-grotesk/600.css'
import '@fontsource/ibm-plex-sans/400.css'
import '@fontsource/ibm-plex-sans/500.css'
import '@fontsource/ibm-plex-sans/600.css'
import '@fontsource/ibm-plex-mono/400.css'
import '@fontsource/ibm-plex-mono/500.css'
import './index.css'
import App from './App.tsx'

// Trackpad pinch over a panel zooms the whole page (the browser's own zoom),
// which breaks the layout until a reload. Block it outside the map; pinching
// over the map still zooms the map, because MapLibre handles that itself.
window.addEventListener(
  'wheel',
  (e) => {
    if (e.ctrlKey && !(e.target as Element | null)?.closest?.('.maplibregl-canvas-container')) e.preventDefault()
  },
  { passive: false },
)
// Safari uses its own gesture events for pinch zoom
for (const type of ['gesturestart', 'gesturechange', 'gestureend']) {
  document.addEventListener(type, (e) => e.preventDefault())
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)

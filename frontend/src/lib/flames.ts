// Animated flame icons drawn on a canvas, used for hotspots when zoomed in.
// There are FLAME_VARIANTS images, each flickering with a different timing,
// and every hotspot uses one of them, so neighbouring flames never move in sync.
import type * as maplibregl from 'maplibre-gl'

export const FLAME_VARIANTS = 4
const SIZE = 96 // canvas pixels; shown at half size on screen (pixelRatio 2)

/** Set by the map: flames only need to animate while they are on screen. */
export const flameState = { active: false }

function drawFlame(ctx: CanvasRenderingContext2D, t: number) {
  const s = SIZE
  ctx.clearRect(0, 0, s, s)

  // flicker: height, sway of the tip and width all change slightly over time
  const h = 0.62 + 0.08 * Math.sin(t * 9.1) + 0.05 * Math.sin(t * 15.7 + 1.3)
  const sway = 0.06 * Math.sin(t * 6.3) + 0.03 * Math.sin(t * 13.9 + 0.7)
  const w = 0.24 + 0.025 * Math.sin(t * 11.3 + 2.1)

  const baseY = s * 0.92
  const cx = s / 2

  // soft glow behind the flame
  const glow = ctx.createRadialGradient(cx, baseY - s * 0.18, 2, cx, baseY - s * 0.18, s * 0.42)
  glow.addColorStop(0, 'rgba(255,140,40,0.55)')
  glow.addColorStop(1, 'rgba(255,90,20,0)')
  ctx.fillStyle = glow
  ctx.fillRect(0, 0, s, s)

  // three nested tongues of fire: red outside, orange, yellow core
  const layers: [number, number, string, string][] = [
    [1, 1, '#ff3d00', '#ff7a1a'],
    [0.72, 0.78, '#ff7a1a', '#ffb347'],
    [0.42, 0.52, '#ffd166', '#fff4c2'],
  ]
  for (const [ls, lh, c1, c2] of layers) {
    const fw = s * w * ls
    const fh = s * h * lh
    const tipX = cx + s * sway * lh
    const tipY = baseY - fh
    const g = ctx.createLinearGradient(0, baseY, 0, tipY)
    g.addColorStop(0, c2)
    g.addColorStop(1, c1)
    ctx.fillStyle = g
    ctx.beginPath()
    ctx.moveTo(cx - fw, baseY - fh * 0.12)
    ctx.bezierCurveTo(cx - fw * 1.05, baseY - fh * 0.55, tipX - fw * 0.35, tipY + fh * 0.25, tipX, tipY)
    ctx.bezierCurveTo(tipX + fw * 0.35, tipY + fh * 0.25, cx + fw * 1.05, baseY - fh * 0.55, cx + fw, baseY - fh * 0.12)
    ctx.bezierCurveTo(cx + fw * 0.8, baseY + fh * 0.04, cx - fw * 0.8, baseY + fh * 0.04, cx - fw, baseY - fh * 0.12)
    ctx.fill()
  }
}

function makeFlameImage(variant: number) {
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = SIZE
  const ctx = canvas.getContext('2d', { willReadFrequently: true })!
  const offset = variant * 1.7 // different timing per variant
  let map: maplibregl.Map | null = null

  const image = {
    width: SIZE,
    height: SIZE,
    data: new Uint8ClampedArray(SIZE * SIZE * 4),
    onAdd(m: maplibregl.Map) {
      map = m
    },
    render() {
      drawFlame(ctx, performance.now() / 1000 + offset)
      image.data = ctx.getImageData(0, 0, SIZE, SIZE).data
      if (flameState.active) map?.triggerRepaint()
      return true
    },
  }
  drawFlame(ctx, offset)
  image.data = ctx.getImageData(0, 0, SIZE, SIZE).data
  return image
}

export function addFlameImages(map: maplibregl.Map) {
  for (let i = 0; i < FLAME_VARIANTS; i++) {
    if (!map.hasImage(`flame-${i}`)) map.addImage(`flame-${i}`, makeFlameImage(i), { pixelRatio: 2 })
  }
}

# FireCal: design rules

Read this before adding or changing any UI. The goal is an interface that looks like it was designed on purpose for this project, not a copy of Google Maps and not the default "AI look" (Inter font, purple gradients, soft white cards everywhere).

## Direction

A dark "operations room" look. The globe is the main element and fills the screen. Panels are dark glass floating over it. Ember orange appears only where something needs attention: fire, the selected area, the main action.

## Colour tokens (defined in `src/index.css`)

| Token | Value | Use |
|---|---|---|
| `--color-ink-950` | `#07090d` | page background, space behind the globe |
| `--color-ink-900` | `#0d1117` | panel background (at 82% opacity, with blur) |
| `--color-ink-800` | `#161b23` | inputs, cards inside panels |
| `--color-ink-700` | `#232a35` | hover states, dividers |
| `--color-line` | `rgb(255 255 255 / 0.08)` | hairline borders (never solid grey borders) |
| `--color-fg` | `#e8ecf2` | main text |
| `--color-fg-muted` | `#8b95a5` | labels, secondary text |
| `--color-ember-500` | `#ff6b1a` | accent: main buttons, selected region, hotspots |
| `--color-ember-300` | `#ffa366` | accent text on dark backgrounds |
| `--color-cool-400` | `#5ba4ff` | values below normal (anomalies) |

Data colours: the calendar uses **cividis**, which is colour-blind safe and does not compete with the ember accent. Above or below normal uses ember vs cool blue, never red vs green.

## Type

- **Space Grotesk**: titles and place names.
- **IBM Plex Sans**: body text and labels.
- **IBM Plex Mono**: every number, coordinate and date. Numbers line up and the app reads as a technical tool.
- No Inter and no Roboto.

## Shape and depth

- Radius: 14px for panels, 10px for inputs and buttons, 6px for small chips.
- Depth comes from a soft shadow plus a 1px inner light line at the top of panels, not from solid borders.
- Panels float 16px away from the screen edges. Nothing is docked edge to edge like Maps.

## Motion (following Emil Kowalski's rules)

- Elements entering: `ease-out`, 180–240 ms. Elements leaving: faster, around 150 ms.
- Animate only `transform` and `opacity`.
- Only animate what explains a change (a panel opening, a number updating). No fade-in on everything.
- Respect `prefers-reduced-motion`.

## Components: use the library, do not hand-roll

| Need | Library |
|---|---|
| Place search (Ctrl+K palette) | `cmdk` + Photon geocoder |
| Popovers, menus, slider | `@base-ui/react` |
| Results panel slide-in | `motion` |
| Bottom sheet on mobile (later) | `vaul` |
| Toasts | `sonner` |
| Animated numbers | `@number-flow/react` |
| Charts | `recharts` (calendar heatmap is our own CSS grid) |
| Icons | `@phosphor-icons/react` (never Material icons) |
| State | `zustand` |

## Copy

UI text is in English, short and concrete ("Analyze area", not "Let's explore your region!"). Units are always shown (km, hotspots).


# Screenpipe Design Guide

## Philosophy

**Cue soft-light: calm layered surfaces, ink controls, one blue focus accent**

Cue turns the ambient trace of human work into memory, models, and agents. The
interface should feel like a quiet, well-lit workspace: cold gray canvas,
white cards floating on hairline boundaries with soft two-stage shadows, and a
single ink color carrying weight.

Ink (#1F2124) is the only "heavy" color — it paints primary buttons and
primary text. Status colors exist only as soft-background pill families.
Phosphor remains the learned signal: it appears only where captured work
becomes useful model context or an agent takes an explicit action.


---

## Core Values

| Value | Description |
|-------|-------------|
| **Privacy First** | Local-first execution and data by default, cloud optional |
| **Human Agency** | Preserve ownership, control, and a visible path back to source material |
| **Open Source** | Inspect, modify, own, clean abstractions and readable codebase |
| **Simplicity** | Clean, minimal interface, powerful abstractions |
| **Radical optimism** | There is no such thing as impossible |
| **Progressive disclosure** | Easy, simple for non technical users but power users can still go deep |

---

## Typography

### Font Stack

| Purpose | Font | Fallbacks |
|---------|------|-----------|
| **UI (sans)** | Inter (400/500/600) | -apple-system, Segoe UI, sans-serif |
| **Data/code (mono)** | JetBrains Mono | SF Mono, IBM Plex Mono, monospace |

### Usage Patterns

- **All UI text**: Inter. Weights 400 for body, 500 for labels/buttons, 600 for headings.
- **Mono is for data only**: timecodes, task names, code, logs — never for buttons or headings.
- No UPPERCASE button typography; sentence case everywhere.


---

## Narrative model

| Visual role | Meaning |
| --- | --- |
| Bone | Human experience and source material |
| Trace grey | Captured evidence and intermediate structure |
| Phosphor | Learned or executable intelligence |
| Ink | The local system, recursion, and durable infrastructure |

The public story is preserving, multiplying, and executing human intelligence.
Do not frame the product as erasing people. Screenpipe handles intimate context,
so agency, ownership, and a visible path back to source material are part of the
interface, not legal footnotes.

## Colors

### Palette

Cold gray layered surfaces with ink controls and one blue focus accent
(cue-tokens v0.4.0, see `app/globals.css`):

- Canvas `#F1F2F3`, sidebar `#FAFAFB`, white cards/popovers
- Ink `#1F2124` for primary buttons and primary text; hover deepens (`#3A3C40`)
- Hairline border `#ECEDEF`, strong `#E0E2E5`
- Accent blue `#0285FF` — small areas only: selection, focus ring, cursor

Status is always a soft-background pill. Five families, each with a soft
background, soft border, and on-soft text token:

| Family | Soft bg | Use |
| --- | --- | --- |
| accent | `#E9F3FF` | informational highlight |
| risk / warning | `#FDF1E5` | needs attention |
| verified / success | `#E8F5ED` | confirmed good |
| failure / destructive | `#FCECEC` | errors, loss |
| unknown / neutral | `#ECEFF0` | rejected/expired/preparing |

No colored card outlines. The default composition is roughly 90 percent
neutrals, small ink masses, and tiny blue accents.

### Where phosphor belongs (unchanged)

Phosphor marks the boundary where capture becomes model context or an agent
acts. It is not a generic accent — see "Narrative model" below and the rules
in this file before using it anywhere new. Its reserved variables
(`--phosphor`, `--phosphor-strong`, `--phosphor-ink`, `--trace`) keep their
existing values in both themes.


---

## Geometry

### Border Radius

| Element | Radius | Token/class |
| --- | --- | --- |
| Controls (buttons, inputs) | 8px | `rounded-lg` (`--radius: 8px`) |
| Cards | 10px | `rounded-[10px]` |
| Panels / modals | 14px | `rounded-panel` |
| Chips | 6px | `rounded-md` |
| Pills / badges | full | `rounded-full` |

### Borders & Shadows

- Hairline 1px borders: `--border` #ECEDEF (light), strong `#E0E2E5`.
- Three elevation levels, theme-aware (`--shadow-card/raised/overlay`,
  consumed as Tailwind `shadow-card` / `shadow-raised` / `shadow-overlay`):
  each is a hairline ring plus two-stage soft shadows that deepen
  automatically in dark mode. Do not hand-roll shadows.


---

## Components

### Buttons

```
- Primary: ink solid (#1F2124), white text; hover deepens — never inverts
- Secondary/outline: white surface, hairline border
- Ghost: transparent, hover shows the accent surface
- Height: 36px (h-9); radius 8; Inter medium; no uppercase
- Focus: 2px ring at 40% opacity
```

### Cards

```
- White surface, hairline border, shadow-card, radius 10
- Padding: 24px (p-6)
```

### Inputs

```
- Field gray background (--input #F2F2F3), hairline border
- Focus: blue border + 2px blue ring at 30% opacity; blue caret
- Inter, not mono; height 36–40px depending on surface
```

### Badges

```
- Soft pill from one of the five status families (bg/border/on-soft tokens)
- rounded-full, xs text, medium weight
```


---

## Motion & Animation

### Principles

- **Fast**: 150ms standard duration
- **Minimal**: Only essential state changes
- **Causal**: Motion should show what changed, what triggered it, and where it went

### Timing

| Animation | Duration |
|-----------|----------|
| Button hover | 150ms |
| Dialog open/close | 150ms |
| Accordion | 200ms |
| Page transitions | 150ms |

### Iteration

Do at least 10 iterations on your animations, at every turn criticise your own design and improve it until it matches the unique brand style

Take screenshots of modern apps with great design you find on internet and use it as inspiration for the UX but apply screenpipe brand style to it.

---

## Brand Voice

### Tone

- Lowercase, casual, direct
- Minimal technical details but power users can go deep
- No marketing fluff
- Show source, trigger, action, destination, and user control where relevant
- Avoid surveillance language and claims that remove human agency

---

## Design Checklist

When creating new UI components:

- [ ] Inter for UI, JetBrains Mono only for data (timecode/code/log)
- [ ] Sentence case; no UPPERCASE button typography
- [ ] Status uses a soft pill — pick one of the five families (accent/risk/verified/failure/unknown)
- [ ] Primary button is ink solid; hover deepens, never inverts
- [ ] Secondary surfaces are white with hairline borders; no colored card outlines
- [ ] Radius scale: control 8 / card 10 / panel·modal 14 / chip 6 / pill full
- [ ] Shadows use shadow-card / shadow-raised / shadow-overlay — never hand-rolled
- [ ] Accent blue #0285FF only for selection, focus ring, cursor — small areas
- [ ] Phosphor only at the capture→context boundary; never as generic accent or success
- [ ] State is understandable without color
- [ ] 150ms transitions
- [ ] Always send screenshot of the new UI in PR bodies or design suggestions in ASCII, if you have access to AI image generation you can also leverage it


---

## Key Files

| Purpose | Location |
|---------|----------|
| Design tokens | `apps/screenpipe-app-tauri/app/globals.css` |
| Tailwind config | `apps/screenpipe-app-tauri/tailwind.config.ts` |
| Color constants | `apps/screenpipe-app-tauri/lib/constants/colors.ts` |
| UI components | `apps/screenpipe-app-tauri/components/ui/*.tsx` |

---

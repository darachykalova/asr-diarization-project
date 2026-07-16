---
name: ASR Admin Console
description: Internal moderation and platform-management panel for an ASR / speaker-diarization / anti-scam call-agent platform
colors:
  working-blue: "#2563eb"
  working-blue-hover: "#1d4ed8"
  working-blue-soft: "#dbeafe"
  working-blue-ring: "#60a5fa"
  alert-red: "#dc2626"
  alert-red-hover: "#b91c1c"
  alert-red-soft: "#fef2f2"
  alert-red-border: "#fecaca"
  clear-green: "#16a34a"
  clear-green-deep: "#15803d"
  clear-green-soft: "#f0fdf4"
  caution-amber: "#eab308"
  ink: "#1f2937"
  body-text: "#4b5563"
  muted-text: "#6b7280"
  faint-text: "#9ca3af"
  surface: "#ffffff"
  canvas: "#f9fafb"
  divider: "#e5e7eb"
  border: "#d1d5db"
  nav-bg: "#1f2937"
typography:
  display:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "normal"
  headline:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, sans-serif"
    fontSize: "1.125rem"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "normal"
  body:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "normal"
  label:
    fontFamily: "ui-sans-serif, system-ui, -apple-system, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.4
    letterSpacing: "normal"
rounded:
  sm: "4px"
  md: "6px"
  lg: "8px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "16px"
  lg: "24px"
components:
  button-primary:
    backgroundColor: "{colors.working-blue}"
    textColor: "{colors.surface}"
    rounded: "{rounded.md}"
    padding: "8px 20px"
  button-primary-hover:
    backgroundColor: "{colors.working-blue-hover}"
    textColor: "{colors.surface}"
    rounded: "{rounded.md}"
    padding: "8px 20px"
  button-danger-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.alert-red}"
    rounded: "{rounded.md}"
    padding: "6px 12px"
  button-danger-ghost-hover:
    backgroundColor: "{colors.alert-red-soft}"
    textColor: "{colors.alert-red}"
    rounded: "{rounded.md}"
    padding: "6px 12px"
  badge-success:
    backgroundColor: "{colors.clear-green-soft}"
    textColor: "{colors.clear-green-deep}"
    rounded: "{rounded.full}"
    padding: "2px 10px"
  badge-error:
    backgroundColor: "{colors.alert-red-soft}"
    textColor: "{colors.alert-red-hover}"
    rounded: "{rounded.full}"
    padding: "2px 10px"
  input-text:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
---

# Design System: ASR Admin Console

## 1. Overview

**Creative North Star: "The Duty Desk"**

This is the screen a moderator has open all shift: a duty desk, not a storefront. Every surface exists to get someone from "what happened" to "what do I do about it" as fast as possible — flagged calls, raw transcripts, speaker identities, platform settings, an audit trail. Nothing here is trying to be liked; it's trying to be trusted and fast.

The system explicitly rejects the playful, bright SaaS-marketing look (PRODUCT.md anti-reference): no gradient heroes, no bouncy celebratory motion, no oversized display type standing in for a value proposition. The product itself exists to catch manipulation and urgency in scam calls — its own interface refuses to use those same tricks on the people running it. Confidence here comes from clarity, consistent placement, and speed, not decoration.

Density is currently light-to-medium: generous white space around card-based sections, one soft shadow tier, a single blue accent reserved for actions. The system today reads as **competent and slightly under-designed** rather than deliberately restrained — every recommendation below builds on what's already true (a real neutral-plus-three-status-color system, flat cards, a plain system sans) rather than proposing a departure from it.

**Key Characteristics:**
- One primary accent (blue), reserved for actions and links — never used decoratively.
- Three status colors (red / green / amber) carry real state, not mood.
- Flat, single-shadow cards throughout; no elevation hierarchy yet.
- System sans-serif everywhere; no display or brand typeface.
- Dense information (tables, filters, timestamps) over illustration or imagery.

## 2. Colors

A restrained, functional palette: one neutral scale that carries almost everything, one blue accent for action, and three status colors that mean something specific every time they appear.

### Primary
- **Working Blue** (`#2563eb`): every primary action — submit buttons, active nav state, links, focus rings. Hover state deepens to `#1d4ed8`. This is the only color in the system used purely for "click here."

### Tertiary
- **Caution Amber** (`#eab308`): reserved for the single "partial" processing status. Used sparingly and only as a status label background, never as an accent.

### Neutral
- **Ink** (`#1f2937`): page headings, the nav bar background, primary text on dark surfaces.
- **Body Text** (`#4b5563`): default paragraph and label copy.
- **Muted Text** (`#6b7280`): secondary text, table meta, helper copy.
- **Faint Text** (`#9ca3af`): placeholders, disabled state, timestamps, empty-state copy.
- **Surface** (`#ffffff`): card and panel backgrounds.
- **Canvas** (`#f9fafb`): page background and table header rows.
- **Divider** (`#e5e7eb`): row dividers, subtle section borders.
- **Border** (`#d1d5db`): input and card borders.

### Named Rules
**The One Accent Rule.** Working Blue is the only color used to mean "you can act here." If a control isn't blue and isn't a status badge, it isn't asking for a click — it's ghost/outline (gray border, colored text on hover) instead. Never add a second decorative accent color.

**The Status-Means-Something Rule.** Red, green, and amber never appear as decoration. Red = danger / destructive / flagged-as-scam. Green = success / clean / done. Amber = partial / in-between. If a color doesn't map to one of these states, don't reach for red, green, or amber.

## 3. Typography

**Body Font:** ui-sans-serif, system-ui, -apple-system, sans-serif (the platform default; no custom typeface loaded)

**Character:** A plain, fast-loading system stack, matching a tool that has no interest in a typographic personality of its own — legibility and speed over voice.

### Hierarchy
- **Display / Headline** (700, `1.5rem`/24px, line-height 1.3): page titles ("Аудиозаписи", "Настройки платформы"). One per page, top-left.
- **Title** (600, `1.125rem`/18px, line-height 1.4): card and section headings within a page ("Транскрипция", modal titles).
- **Body** (400, `0.875rem`/14px, line-height 1.5): table cells, form labels, paragraph copy, button labels. The workhorse size — the large majority of text on any screen is this size.
- **Label** (500, `0.75rem`/12px, line-height 1.4): status badges, table meta (job IDs, timestamps), helper/hint text under inputs.

### Named Rules
**The No-Display-Font Rule.** This system has no hero typography and should not gain one. A page title at 24px/700 is the largest text anywhere; anything bigger reads as marketing, not administration.

## 4. Elevation

Flat by default, with a single soft shadow tier separating a card from the page canvas. There is currently no elevation hierarchy — every card, modal, and dropdown uses the same shadow weight regardless of how "on top" it visually is (a page-level card and a modal both read at the same depth). This is an honest gap worth closing eventually (a modal or an open dropdown should sit visibly above a page card), but it is not fabricated here as if it already existed.

### Shadow Vocabulary
- **Card** (`box-shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)` — Tailwind `shadow`): the default resting state for every card, table container, and filter panel.
- **Raised** (`box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)` — Tailwind `shadow-lg`): used inconsistently today for the nav dropdown and toasts; the closest thing to a "floating above the page" tier that exists.
- **Modal** (`box-shadow: 0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)` — Tailwind `shadow-xl`): the confirm dialog only.

### Named Rules
**The Flat-By-Default Rule.** Surfaces are flat at rest. A shadow only appears to separate a floating element (modal, dropdown, toast) from the page beneath it — never as a decorative border-replacement on a card that sits in normal document flow.

## 5. Components

### Buttons
- **Shape:** 6px corner radius (`rounded` / `rounded-md`).
- **Primary:** Working Blue background, white text, `8px 20px` padding, deepens to `#1d4ed8` on hover.
- **Danger / destructive:** transparent background, Alert Red text and border, fills to a soft red tint (`#fef2f2`) on hover. Reserved for delete actions, always paired with a confirm dialog before the destructive call fires.
- **Ghost / secondary:** transparent background, gray border, gray text, fills to `canvas` gray on hover.
- **Press feedback:** every button in the system scales to 0.97 on `:active` (a 2026-07-16 addition, applied consistently across the app), with `prefers-reduced-motion` dropping the scale but keeping the color transition.

### Badges (status labels)
- **Style:** fully rounded (`rounded-full`), `2px 10px` padding, 12px/500 label type.
- **State:** background is the status color's `-soft` tint, text is the status color's `-deep`/`-hover` shade (never the raw saturated value on a light background — that's a contrast failure waiting to happen).

### Cards / Containers
- **Corner style:** 8px radius (`rounded-lg`).
- **Background:** Surface white on Canvas gray page background.
- **Shadow strategy:** the Card tier from Elevation; no border in addition to the shadow (don't double up shadow + border on the same card).
- **Internal padding:** 16–24px depending on density (filter panels use 16-20px, detail pages use 20-24px).

### Inputs / Fields
- **Style:** 1px Border-gray stroke, white background, 6px radius, `8px 12px` padding.
- **Focus:** border color shifts toward Working Blue with a 2px blue ring (`focus:ring-2 focus:ring-blue-400/500`) — this is the only place a "glow" treatment exists in the system, and it should stay that way.
- **Disabled:** 50% opacity, no other treatment change.

### Navigation
- **Style:** a single dark (`nav-bg` `#1f2937`) top bar, white/gray-400 text, the active route underlined rather than pill-highlighted. A secondary "Управление" dropdown groups admin-only routes behind one extra click, keyed off role.
- **Dropdown:** anchored to its trigger (scale + fade from the top-left, not center), matching the Raised shadow tier.
- **Mobile treatment:** not yet designed — the nav bar does not currently adapt below desktop widths.

### Toasts
- **Style:** solid status-color background (not the soft tint used elsewhere — toasts are the one place the saturated color appears on white text), white text, `rounded-lg`, Raised shadow, bottom-right corner stack.
- **Behavior:** enters/exits via a translate + opacity transition (not a keyframe animation, so a rapid burst of toasts stays interruptible), auto-dismisses after 6 seconds or on manual close.

## 6. Do's and Don'ts

### Do:
- **Do** keep Working Blue as the only action-accent color; every other color on screen is either neutral or a status meaning.
- **Do** use the `-soft` tint + `-deep`/`-hover` text pairing for any new status badge, never the raw saturated color as a badge background.
- **Do** respect `prefers-reduced-motion` on every new animation: drop movement/scale, keep the opacity or color transition.
- **Do** anchor any new popover/dropdown/tooltip to its trigger with a scale+fade entrance, matching the nav dropdown pattern, never a center-scale (modals are the one exception — they stay centered).
- **Do** use the system sans stack and the four-step type scale (24/18/14/12px) for any new screen; don't introduce a fifth size without a clear reason.

### Don't:
- **Don't** add a second decorative accent color alongside Working Blue — PRODUCT.md's anti-reference is exactly this kind of "playful/bright SaaS" move.
- **Don't** use `border-left`/`border-right` as a colored accent stripe on cards or list rows.
- **Don't** use gradient text or a gradient hero background anywhere in this product.
- **Don't** introduce bouncy/elastic easing or celebratory motion (confetti, spring-overshoot) — every animation in this system uses a controlled ease-out, never a bounce.
- **Don't** give any single page a display-sized headline above 24px/700 — that reads as a marketing page, not an administration screen.
- **Don't** stack a shadow and a border on the same card; pick one depth cue.

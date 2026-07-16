---
target: frontend/src/pages/CallSimulatorPage.tsx
total_score: 19
p0_count: 2
p1_count: 2
timestamp: 2026-07-16T12-04-44Z
slug: frontend-src-pages-callsimulatorpage-tsx
---
Method: dual-agent (isolated sub-agents)

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 1 | No "connecting" vs "connected" distinction; manual end leaves the log silently frozen with no closing marker |
| 2 | Match Between System and Real World | 3 | Phone metaphor is clear, but no ringing/caller-identity cues support the "call" framing |
| 3 | User Control and Freedom | 2 | Only exit is "Завершить" — no mute, no way to clear the log for a fresh demo without reloading |
| 4 | Consistency and Standards | 3 | Press-feedback/color mostly match DESIGN.md, but red is used for a neutral "end call" action |
| 5 | Error Prevention | 1 | No debounce/in-flight guard — rapid double-click races `start()`/`stop()`'s ref-based session tracking |
| 6 | Recognition Rather Than Recall | 3 | The one-line instruction above the button is genuinely helpful and well-placed |
| 7 | Flexibility and Efficiency of Use | 1 | No keyboard shortcut, no way to copy/replay the transcript |
| 8 | Aesthetic and Minimalist Design | 3 | Spare and on-brand, but the empty pre-call log reads as a rendering glitch, not intentional minimalism |
| 9 | Error Recovery | 1 | Mic-denied and WS-error both dump a raw string into the same log stream as agent speech — no color, icon, or retry |
| 10 | Help and Documentation | 1 | No explanation that this streams real audio to a backend before the browser's native mic prompt appears |
| **Total** | | **19/40** | **Poor — major UX overhaul needed; core status/error visibility broken** |

## Anti-Patterns Verdict

**LLM assessment**: Reads as an internal test harness shipped from a first draft, not consumer-AI gloss — the crossfade/pulse/fade-in motion is restrained and DESIGN.md-compliant. The empty white log card, missing empty-state copy, and identical treatment of errors/system messages/agent speech read as "unfinished," not "over-decorated."

**Deterministic scan**: CLI mode (source-only) returned 0 findings. Browser-injected scan found 1 real hit: `low-contrast` — white text on the `bg-green-600` "Позвонить" button, 3.3:1 (needs 4.5:1). Confirmed real (button text is default-size, no large-text exception applies); the CLI/browser discrepancy is a known coverage gap (CLI can't compute rendered contrast), not a false positive either way.

## Overall Impression

The happy path (click, mic access, agent answers, transcript fades in) genuinely lands — it feels like a real call. But the page falls apart exactly where a real demo goes wrong: errors and system messages are visually identical to normal agent speech, ending a call gives no closing beat, and nothing guards against a rapid double-click race. For a tool whose whole purpose is testing an anti-scam agent's failure modes, the page itself has no visible failure-mode handling.

## What's Working

- The `active:scale-[0.97]` press feedback and green→red crossfade on the toggle exactly match the system's established button vocabulary — no new decoration invented.
- The one-sentence instruction above the button earns its place for an occasional-use tool.
- The log line fade-in respects `prefers-reduced-motion`, unlike a lot of AI-generated chat UIs.

## Priority Issues

**[P0] Log doesn't distinguish errors from agent speech**
- Why it matters: mic-denied and WebSocket-error messages render as identical gray text to normal "Агент:" lines — a failed demo looks the same as a working one at a glance, which is the one thing this internal QA tool can't afford.
- Fix: give error/system lines a distinct treatment — reuse DESIGN.md's `alert-red`/`alert-red-soft` badge pattern, separate from agent turns.
- Suggested command: `/impeccable harden`

**[P0] No closing log entry when the user manually ends the call**
- Why it matters: the agent-hangup and dropped-connection paths both push a closing line, but manual "Завершить" doesn't — the transcript looks frozen/unfinished, leaving no confirmation the call actually stopped.
- Fix: push a neutral "— Звонок завершён —" line in `stop()` when triggered by the user.
- Suggested command: `/impeccable harden`

**[P1] No debounce/in-flight guard on start/stop**
- Why it matters: rapid double-clicking the toggle can race two WebSocket/AudioContext lifecycles against each other via the same refs, with no visible error.
- Fix: add a `connecting` state distinct from `active`; disable or ignore the toggle while a connect/teardown is in flight.
- Suggested command: `/impeccable harden`

**[P1] Empty pre-call log has no placeholder copy**
- Why it matters: a first-time user sees a bare white box with no border or label — reads as broken, not empty-by-design.
- Fix: add faint placeholder text ("Здесь появится расшифровка звонка") using DESIGN.md's `faint-text`.
- Suggested command: `/impeccable clarify`

**[P2] Toggle button color has two problems**
- Why it matters: the green "Позвонить" state fails contrast (3.3:1, detector-confirmed, needs 4.5:1); separately, the red "Завершить" state borrows the system's danger color for a neutral action, drifting from DESIGN.md's "Status-Means-Something" rule (red = destructive/flagged elsewhere in the app).
- Fix: darken the green to pass contrast, or swap it per DESIGN.md's token; use a neutral/gray "Завершить" state instead of red since ending a test call isn't destructive.
- Suggested command: `/impeccable colorize`

## Persona Red Flags

**Jordan (Confused First-Timer)**: nothing frames what's about to happen before the browser's native mic-permission prompt — no mention that real audio streams to a backend. The blank white log box with no placeholder copy reads as a broken page on first sight.

**Riley (Deliberate Stress Tester)**: double-clicking "Позвонить" fast has no debounce (ref-based race). Denying the mic permission produces a plain-gray error line identical in styling to normal chat — easy to miss while scrolling. No `beforeunload` guarantee that mic/WS actually close if the tab is closed mid-call.

## Minor Observations

- No timestamp on any log line.
- Log container has no `max-h`/`overflow` — will grow unbounded down the page as a call gets longer.
- Keyboard focus ring on the toggle button not verified live.
- Page title correctly stays within DESIGN.md's 24px/700 rule — no oversized display type.

## Questions to Consider

- What if the log distinguished agent/system/error as three visually distinct row types, like a real call log, instead of one plain text stream?
- What if there were a lightweight "Соединение…" micro-state between click and mic-granted, so a first-time user never wonders if the click registered?
- What if ending a call surfaced a one-line verdict summary (matching the anti-scam detector's own output) instead of silently reverting to idle?

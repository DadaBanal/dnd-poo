# HANDOFF — SQL01 → Cloud Build, WS36, 15 Oct 2026 (PMC Vitals Console: the glass and one-shadow bans are lifted; build the login screen and the chrome to the new rules)

**Dada, 15 Oct 2026, asked whether the two bans could go *"if it will make the design aesthetically better and wont
affect efficiency and performance"*, then: *"lift it"*. Published to his design system as **Version 7**
(`https://claude.ai/artifact/M6C4r6FT5B2CzzgWzdyNGB`, version id `1792015651-0289`). Read `project/README.md` and
`project/tokens.json` again before building — **the two items of the 7d037f5 review that were rule breaks are now
rules with a shape.** Nothing on the host changed.**

## 1. What changed in the system

| Was | Now |
|---|---|
| *"There is no glass, frosting, translucency or blur anywhere in this system, and none may be added."* | **Glass permitted on overlays and fixed chrome only** — top bar, menus and hover panels, dialogs, the image viewer's scrim. **Never on a table, a list, a card, or anything inside a scrolling data surface.** |
| *"One shadow. `shadow-card`, and only that."* | **Three elevation levels:** `shadow-card` (cards at rest, unchanged), `shadow-raised` (a card while hovered or dragged), `shadow-overlay` (menus, hover panels, dialogs, the viewer). A level means *this is on top of that* — never to rank one report card above another. |
| Gradients | **Never banned, unchanged.** (My review had implied otherwise; Dada corrected it.) |

## 2. The new tokens — exact values

| Token | Value | Usage |
|---|---|---|
| `chrome.glass` | `rgba(14, 21, 32, 0.85)` both themes | The glass tint. **Opacity 0.85 is solved, not chosen:** the lowest at which both onDark inks clear 4.5:1 over the worst background glass can sit on (white `surface`, composite `#323841`). Measured: `ink.onDark` **11.81:1**, `ink.onDark.muted` **4.58:1**. Text on glass takes the onDark set. |
| `chrome.glass.solid` | `#0E1520` (= `chrome.deep`) | The fallback (below). |
| `glass-blur` | `12px` | The backdrop blur behind `chrome.glass`, **and the cap**. |
| `shadow-raised` | `0 4px 12px rgba(22, 32, 43, 0.14)` | Hover/drag on a card. |
| `shadow-overlay` | `0 12px 32px rgba(0, 0, 0, 0.22)` | Overlays. **This is exactly the drop shadow you already used** — the review's "second shadow" finding becomes correct use, provided it is on an overlay. |

## 3. The performance guard — his condition, built in

Blur is not free: a backdrop blur repaints whatever moves behind it, on every scroll (every source checked agrees it
is GPU work). Shadows are effectively free. So glass carries two guards and **both are required**:

```css
.glass { background: var(--chrome-glass); backdrop-filter: blur(var(--glass-blur)); }
@supports not (backdrop-filter: blur(1px)) { .glass { background: var(--chrome-glass-solid); } }
@media (prefers-reduced-transparency: reduce) { .glass { background: var(--chrome-glass-solid); backdrop-filter: none; } }
```

If the ward PCs stutter, that fallback is the switch — one media rule, nothing redesigned.

## 4. What this changes in the 7d037f5 review

- **Blur (8 elements):** each one is either on an overlay or fixed chrome — keep it, retoken it to `chrome.glass` +
  `glass-blur` with the fallback — or it is on a card, list or table, where it is still out. Report which was which.
- **Shadows (4 values):** `shadow-card` and the grape tick stand; the `0 12px 32px` drop becomes `shadow-overlay` where
  it is on an overlay; **the blue glow with the white inset ring is still not in the system** — use the grape tick or
  `shadow-raised`.
- **The login screen** — the review's critical finding — is now the obvious first place to use the lifted rules:
  build it to the tokens, a glass card over the chrome if it reads better, plain *Sign in* for everyone with the
  break-glass wording only on its own route, and **both fields with real labels** (they are unnamed today: WCAG 3.3.2,
  4.1.2).
- Everything else in the review stands unchanged: error pages into the chrome, the three unnamed requisition pickers,
  the Movements paragraph, the double *All* chip, the 800px clipping, Ember on *break-glass* and Grape on *BETTER*.

`PSA_BIZBOX_WRITE_ODBC` unset; nothing on the host changed.

Status: open

# Job 02 — the rest of the 7d037f5 design review

**First:** read `platform/psa-spine/CLAUDE.md` — it says which skills to load and the rules every job follows.

**Source:** `docs/handoffs/HANDOFF-sql01-cloud-WS36-20261015-design-review-7d037f5.md`, read with
`HANDOFF-sql01-cloud-WS36-20261015-vitals-bans-lifted.md` (the bans changed after the review).

**Do, in this order:**
1. **The 8 blur elements:** on an overlay or fixed chrome → retoken to `chrome.glass` + `glass-blur` with the
   fallback; on a card, list or table → remove. Record which was which.
2. **Shadows:** the `0 12px 32px` drop → `shadow-overlay` (overlays only); the blue glow with the white inset ring →
   the grape tick or `shadow-raised`.
3. **One error template** in the desk's chrome for 403/404, keeping the existing sentence and a way back.
4. **Label the three required pickers** (`warehouse_src`, `warehouse_dst`, `doc_date`) on every document form, and
   the global search (`aria-label`).
5. Minors: drop the Movements paragraph; one *All* chip; the 800px clipping of *New ticket* and the Purchase Orders
   header; *break-glass* to `status.warning`, *BETTER* off Grape.

**Done when:** the computed-style checks are re-run on the throwaway desk (blur count, distinct shadows, unnamed
controls) and each reads as the system allows; suite green; committed; one runbook paragraph.

Status: open

# Job 01 — the login screen, to PMC Vitals Console v7

**First:** read `platform/psa-spine/CLAUDE.md` — it says which skills to load and the rules every job follows.

**Why:** Dada, 15 Oct: *"we can do better on the login screen."* It is the first screen every user meets and the
review's one critical finding (`docs/handoffs/HANDOFF-sql01-cloud-WS36-20261015-design-review-7d037f5.md` §2–3).

**Do:**
1. Build `/login` to the Vitals tokens (v7 — glass now allowed on fixed chrome; see
   `HANDOFF-sql01-cloud-WS36-20261015-vitals-bans-lifted.md`). Plain *Sign in* for everyone; the break-glass wording
   ("for the on-call rota, when the WAN is down") only on the break-glass route.
2. Give both fields real `<label for>` — they are unnamed `textbox` today (WCAG 3.3.2, 4.1.2).
3. Glass, if used, with the required `@supports` and `prefers-reduced-transparency` fallback.

**Done when:** the suite passes; reviewed on the throwaway desk with `design:design-critique` and
`design:accessibility-review`; committed and pushed; one paragraph in the runbook. **The restart is Dada's word.**

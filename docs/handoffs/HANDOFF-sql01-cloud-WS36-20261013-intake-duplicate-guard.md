# HANDOFF — SQL01 → Cloud Build (WS36) — 13 Oct 2026
## `_recent_same_subject` suppresses genuinely new requests. Three faults, 30 messages.

**From:** SQL01 (host-side), for Dada
**To:** WS36 / Cloud Build — this is your code, `psaspine/intake.py`
**Raised by:** Dada, 13 Oct 2026, *"this billing ticket isnt appearing"*
**Status:** nothing changed. No write to `psa.intake_message`, the desk, or either mailbox.
**Evidence:** every number below is **MEASURED** from `PMC_PSA` on `DND-SQL01\PMC_SS`,
13 Oct 2026 ~17:10 PH. Controls at the end.

---

## 1. The report, and what actually happened

A Billing email reached `support@pmcne.ph` at **16:43 PH** and no ticket appeared.
(Dada's Outlook renders +3 h, so his "7:43 PM" is 16:43. Not a clock fault.)

The desk **did** import it. The pickup is healthy — all five tasks ran at 17:00:00, result 0,
next 17:01:01, triggers PT1M. The row:

| column | value |
|---|---|
| `received_at` | 2026-10-13 16:43 |
| `from_address` | `pmcbilling108@gmail.com` |
| `channel` | helpdesk |
| `disposition` | **DUPLICATE** |
| `work_item_id` | **NULL** |
| `duplicate_of` | the 11:31 message from the same sender |
| `run_id` | `mail-support-pmcne-ph-20261013084404` |

The text was **appended as a note to `PMC-001580`** — the 11:31 ticket, which is a *different
doctor*. Nothing was lost; it was filed onto the wrong person's ticket and no new ticket was raised.

---

## 2. The rule

`psaspine/intake.py`, `_recent_same_subject()` at ~line 540, called from the decision site at
~line 708. Reproduced as it stands:

```python
cutoff = (at - DUPLICATE_WINDOW).isoformat(sep=" ", timespec="minutes")
return conn.execute(
    "SELECT message_id, work_item_id FROM intake_message"
    "  WHERE from_address = ? AND subject = ? AND received_at >= ?"
    "    AND work_item_id IS NOT NULL"
    "  ORDER BY received_at DESC LIMIT 1",
    (sender, subject, cutoff)).fetchone()
```

`DUPLICATE_WINDOW = timedelta(hours=24)` (line 51).

Your own docstring calls it *"the weaker guard, used only when there is no thread header.
INFERRED."* The judgement was sound; the match key is too blunt for how PMC actually sends mail.

---

## 3. Fault 1 — a reused subject line is not a duplicate

**The match key is sender + exact subject + 24 h. Nothing about content.**

PMC departments use a **standing subject line**, one mail per case. Billing sends the same
subject for every doctor. The normaliser also strips `Re:`, so a reply's subject becomes
byte-identical to the original's — **22 characters in both rows**, confirmed equal in SQL
(`CASE WHEN d.subject = p.subject`).

So the second case of the day from any such sender collapses onto the first case's ticket.

**MEASURED, all 30 DUPLICATE rows:**

- **30 of 30** had a subject byte-identical to the parent's
- **30 of 30** fell inside the 24 h window, so the rule fired exactly as written
- **30 of 30** were appended as a note to the parent's ticket — **none raised its own ticket**

Dispositions across the whole table (478 rows):

| disposition | rows |
|---|---|
| NEW_TICKET | 325 |
| APPENDED | 105 |
| **DUPLICATE** | **30** |
| UNCLASSIFIED | 18 |

### The exposure is structural, not a one-off

Sender + subject pairs used **three or more times** — every one of these is exposed:

| sender | uses | subject length |
|---|---|---|
| `premieremedfm252022@gmail.com` | 11 | 21 |
| `clariza.angeles@pmcne.ph` | 6 | 37 |
| `katherine.deguzman@pmcne.ph` | 5 | 30 |
| `nuevaecijastone@gmail.com` | 5 | 16 |
| `clariza.angeles@pmcne.ph` | 4 | 30 |
| `pmcdialysis1997@gmail.com` | 4 | 27 |
| `shane.laureano@pmcne.ph` | 3 | 34 |
| `pmc2decho@gmail.com` | 3 | 47 |
| `pmcbilling108@gmail.com` | 3 | 22 |
| `laserandvisioncenter@gmail.com` | 3 | 13 |

Tickets that absorbed other people's requests:

| ticket | messages absorbed |
|---|---|
| PMC-000148 | 3 |
| PMC-000303 | 3 |
| PMC-000407 | 3 |
| PMC-000386 | 2 |
| PMC-000150, 000153, 000165, 000177, 000179, 000192, 000232, 000247, 000263, 000265, 000288, 000310, 000361, 000412, 001461, 001476, 001485, 001578, 001580 | 1 each |

**Subject text is deliberately absent from this handoff** — lengths only, per the record's
content fence. The lengths are enough to see the collision shape.

---

## 4. Fault 2 — the parent may arrive *after* the child

The query has a **lower bound only** (`received_at >= cutoff`). No upper bound, and no
`received_at < at`. Combined with `ORDER BY received_at DESC LIMIT 1`, a message can be filed as
a duplicate of a message that **had not been received yet**.

**MEASURED: 4 of 30 have a negative gap** — the suppressed message arrived *before* its parent:

| # | suppressed at | sender | gap to parent | parent |
|---|---|---|---|---|
| 1 | 2026-09-30 07:49 | `pmcadmitting101@gmail.com` | **−49 min** | PMC-000179 |
| 3 | 2026-09-30 17:23 | `pmcradiologymri2018@gmail.com` | **−15 min** | PMC-000192 |
| 4 | 2026-10-01 06:00 | `encoder@premieremedicalcenter.net` | **−22 min** | PMC-000150 |
| 5 | 2026-10-01 06:34 | `nuevaecijastone@gmail.com` | **−48 min** | PMC-000148 |

This bites whenever a drop is imported out of receipt order, which `import_drop` does not
guarantee — it iterates `sorted(drop.iterdir())`, i.e. **filename order, not time order**.

Minimum fix regardless of anything else: `AND received_at < ?` bound at `at`.

---

## 5. Fault 3 — it crosses channels and boards

`_recent_same_subject` filters on sender and subject only. **Not channel, not board.**

**MEASURED:** `PMC-000148` was raised from the **support** channel. Row 7 —
`nuevaecijastone@gmail.com`, 2026-10-01 15:52, **helpdesk** channel — was suppressed against it
and its text appended to that support ticket.

So a Helpdesk request can be silently absorbed into a PMC Service Board ticket, and the two
boards have different queues, prefixes and owners. A member working Helpdesk will never see it.

---

## 6. The full 30, for your test fixtures

No subjects, no bodies, no attachment names. `identical?` is the SQL comparison of the two
stored subjects.

| # | suppressed at | sender | channel | subj len | identical? | gap | parent |
|---|---|---|---|---|---|---|---|
| 1 | 2026-09-30 07:49 | `pmcadmitting101@gmail.com` | helpdesk | 35 | yes | −49 min | PMC-000179 |
| 2 | 2026-09-30 09:31 | `pmcradiologymri2018@gmail.com` | helpdesk | 34 | yes | 6 min | PMC-000177 |
| 3 | 2026-09-30 17:23 | `pmcradiologymri2018@gmail.com` | helpdesk | 17 | yes | −15 min | PMC-000192 |
| 4 | 2026-10-01 06:00 | `encoder@premieremedicalcenter.net` | support | 68 | yes | −22 min | PMC-000150 |
| 5 | 2026-10-01 06:34 | `nuevaecijastone@gmail.com` | support | 16 | yes | −48 min | PMC-000148 |
| 6 | 2026-10-01 13:59 | `nuevaecijastone@gmail.com` | support | 16 | yes | 6.6 h | PMC-000148 |
| 7 | 2026-10-01 15:52 | `nuevaecijastone@gmail.com` | **helpdesk** | 16 | yes | 8.5 h | PMC-000148 |
| 8 | 2026-10-01 16:46 | `pmc.nursingoffice@gmail.com` | helpdesk | 31 | yes | 14 min | PMC-000153 |
| 9 | 2026-10-02 02:37 | `gladys.macario@pmcne.ph` | helpdesk | 31 | yes | 7 min | PMC-000165 |
| 10 | 2026-10-02 09:33 | `lester.ballesteros@pmcne.ph` | helpdesk | 16 | yes | 6.1 h | PMC-000232 |
| 11 | 2026-10-03 06:23 | `aj.monton@pmcne.ph` | helpdesk | 14 | yes | 60 min | PMC-000247 |
| 12 | 2026-10-05 01:26 | `lalaine.libid@pmcne.ph` | helpdesk | 33 | yes | 0 min | PMC-000263 |
| 13 | 2026-10-05 10:18 | `pmc2decho@gmail.com` | helpdesk | 47 | yes | 37 min | PMC-000265 |
| 14 | 2026-10-05 16:44 | `premieremedfm252022@gmail.com` | helpdesk | 21 | yes | 88 min | PMC-000303 |
| 15 | 2026-10-05 16:47 | `premieremedfm252022@gmail.com` | helpdesk | 21 | yes | 91 min | PMC-000303 |
| 16 | 2026-10-06 03:28 | `clariza.angeles@pmcne.ph` | helpdesk | 37 | yes | 19.0 h | PMC-000310 |
| 17 | 2026-10-06 09:41 | `premieremedfm252022@gmail.com` | helpdesk | 21 | yes | 18.4 h | PMC-000303 |
| 18 | 2026-10-06 10:26 | `pmcdialysis1997@gmail.com` | helpdesk | 27 | yes | 20.6 h | PMC-000288 |
| 19 | 2026-10-07 08:57 | `clariza.angeles@pmcne.ph` | helpdesk | 37 | yes | 15 min | PMC-000386 |
| 20 | 2026-10-07 09:42 | `premieremedfm252022@gmail.com` | helpdesk | 21 | yes | 10 min | PMC-000361 |
| 21 | 2026-10-08 06:57 | `clariza.angeles@pmcne.ph` | helpdesk | 37 | yes | 22.2 h | PMC-000386 |
| 22 | 2026-10-08 12:13 | `laserandvisioncenter@gmail.com` | helpdesk | 13 | yes | 24 min | PMC-000412 |
| 23 | 2026-10-08 13:01 | `premieremedfm252022@gmail.com` | helpdesk | 21 | yes | 2.0 h | PMC-000407 |
| 24 | 2026-10-08 14:27 | `premieremedfm252022@gmail.com` | helpdesk | 21 | yes | 3.5 h | PMC-000407 |
| 25 | 2026-10-08 14:49 | `premieremedfm252022@gmail.com` | helpdesk | 21 | yes | 3.8 h | PMC-000407 |
| 26 | 2026-10-09 08:27 | `shane.laureano@pmcne.ph` | helpdesk | 34 | yes | 22 min | PMC-001461 |
| 27 | 2026-10-09 16:24 | `pmc.nursingoffice@gmail.com` | helpdesk | 13 | yes | 8 min | PMC-001476 |
| 28 | 2026-10-10 08:12 | `clariza.angeles@pmcne.ph` | helpdesk | 30 | yes | 4.1 h | PMC-001485 |
| 29 | 2026-10-13 15:13 | `pmcradiologymri2018@gmail.com` | helpdesk | 7 | yes | 3.8 h | PMC-001578 |
| 30 | 2026-10-13 16:43 | `pmcbilling108@gmail.com` | helpdesk | 22 | yes | 5.2 h | PMC-001580 |

---

## 7. Where this sits against Dada's existing ruling

He has already ruled once on this guard. **2 Oct 2026**, recorded in your own docstring: two
unrelated requests from one ward, both with no subject, are **two requests** — matching them on
`""` would file the second as a note on the first.

**This is the same ruling, one step further on.** An empty subject is not an identity. Neither is
a *reused* subject. The principle he stated is that the subject line is not what makes two mails
the same request, and the code currently treats it as exactly that whenever it is non-empty.

**INFERRED, so challenge it:** the 2 Oct fix treated the empty subject as the special case. The
measurement says the general case is the problem — on this estate, a standing subject line is the
norm, not the exception. 10 sender+subject pairs are in active reuse.

---

## 8. What SQL01 suggests, for you to judge

Not prescriptive — you own `intake.py`. In order of confidence:

1. **Bound the window at both ends.** `AND received_at < ?` at `at`. Fault 2 is unambiguous and
   independent of any policy question. Cheap, safe, no behaviour change in the normal case.
2. **Add channel (and board) to the match key.** Fault 3 is also unambiguous: a Helpdesk mail
   should never be absorbed into a Service Board ticket.
3. **Stop matching on subject alone.** This is the policy decision and it is Dada's, not ours.
   The options SQL01 can see:
   - require the **body** to be substantially the same (a resend, not a new case) — a normalised
     hash of the body would catch a true resend and let a new case through;
   - keep the suppression but **raise a ticket anyway**, cross-linked, so nothing is invisible;
   - **narrow the window** hard — a true accidental resend is minutes, not 24 hours. 14 of the 30
     were over an hour apart; 8 were over 4 hours.
4. **Whatever you choose, make the DUPLICATE path visible.** Right now it writes a note and
   returns. Nobody is told. A member cannot tell a suppressed request from one that never
   arrived — which is exactly how this surfaced, by Dada noticing a missing ticket by eye.

A regression test from row 30 is the clean one: two messages, same sender, identical subject,
5.2 h apart, different bodies → **two tickets**.

---

## 9. Controls (R3 — absence is not a finding without one)

| control | result | reads |
|---|---|---|
| `disposition = 'ZZZ_NOPE'` | 0 | a value that cannot exist is absent ✔ |
| `disposition = 'NEW_TICKET'` | 325 | the method can see what is there ✔ |
| `from_address = 'zzz-nobody@nowhere.invalid'` | 0 | ✔ |
| the 30-row join | 30 of 30 matched a parent | no orphan `duplicate_of` ✔ |

Negative controls paired with positive ones throughout, so *not found* and *cannot see* stay
distinguishable.

Earlier in the same diagnosis two of my own queries failed and are worth you knowing, because the
schema is not what a reader assumes: `psa.intake_message` has **no** `status` or `state` column
(the column is `disposition`), and `psa.work_item` has **no** `created_at`.

---

## 10. Open on Dada's word, not acted on

`PMC-001580` carries Billing's second doctor as a note. Dada was offered the option of raising it
as its own ticket and has **not** taken it — he chose this handoff instead. The note stays where
it is until he says otherwise. The other 29 are in the same state.

**Nothing on this host was changed.** Read-only throughout.

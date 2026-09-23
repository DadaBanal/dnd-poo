# ENVIRONMENT.md — find your row before you do anything

This is a **pointer, not the manifest**. The master lives in the programme
record: OneDrive `Documents/Claude/ENVIRONMENT.md`, beside `PMC_START_HERE.md`
and the per-machine state files it points to. Hostnames only, every cell dated,
a cell older than 14 days reads as NOT VERIFIED. Nothing here is copied from it,
so nothing here can drift from it.

**Which row am I?**

- Your opening message names a row (Main, SQL01, Cloud Build, 365 Desk) → that is you.
  Your row and your bucket are in that message; act on those and nothing else.
- You are **Main** → read the master through the Microsoft 365 connector
  (search `Documents/Claude` for `ENVIRONMENT.md`, then read it) before anything else.
- cwd is `/home/user/dnd-poo` and no row is in your opening message → you are an
  unnamed cloud session: say "I have no row" and act on nothing.
- Hostname `DND-SQL01` → a host session. Load the record skills first (`pmc-estate`
  before anything on the estate) and take the record's write lock before writing.
  `DESKTOP-RANFMVE` → MEL: stop and ask.

**The sentence**, instead of "I am not connected here":
*"I am ‹row›. ‹Other row› has that route. I am writing
`HANDOFF-‹me›-‹them›-‹WSnn›-YYYYMMDD.md`."* Template: `docs/handoffs/`.

No cloud session has a network route to `DND-SQL01\PMC_SS` or `PMC-ORTHANC01`
(MEASURED, 10 Sep 2026; still true 23 Sep). Do not try; hand off.

**How a cloud session talks to the host** (VERIFIED 23 Sep 2026 from
code.claude.com/docs/en/cross-session-messaging and /claude-code-on-the-web):

- **The host starts it.** A host session connected to Remote Control can see your
  cloud sessions and message one by name. The message carries a reply address, so
  the cloud session can answer. A cloud session cannot start that conversation: its
  agent list is empty (MEASURED here, 23 Sep).
- **One-way from any machine:** `claude -p "text" --cloud <session-id>` queues a
  message into a cloud session. Good for a script or hook on the host.
- **Teleport** (`claude --teleport <session-id>`) copies a *cloud* session down to a
  machine that has a clean checkout of this repo. It does not reach a host session,
  and work done in the copy stays there.
- Self-hosted cloud environments need a Team or Enterprise plan; this account is Max.

Messages travel through Anthropic's servers as plain text: no patient identifier,
credential or internal address in one, ever.

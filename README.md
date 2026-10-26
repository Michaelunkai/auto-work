# AutoWork v2.0.0 — The Ultimate Autonomous Job Application Runner

One executable finds brand-new, verified, relevant employers and sends Michael a
junior-role application email to each — automatically, fail-closed, never twice.
v2.0.0 is a discovery rehaul: a new drushim lane that reads the full live job
market straight out of the board's embedded data (title, company, experience
level, scope, freshness), playbook-grade accuracy filters, reply-probability
send ordering, self-healing gates, and UTF-8 hardening so Hebrew never crashes
a child process again.

## Quick start (double-click)

- **Run-AutoWork.cmd** — one batch: find + send up to 5 applications, receipt at the end.
- **Run-AutoWork-Forever.cmd** — continuous: batches of 5, 25-min cooldown,
  100/day cap, self-email after every send. Stop with Ctrl+C or window close.

Useful variants (AutoWork.exe):

- `AutoWork.exe run --count 3` — send exactly 3 applications
- `AutoWork.exe run --count 1 --dry-run` — full pipeline, sends nothing, validates leads
- `AutoWork.exe discover --lanes drushim --limit 20` — research only, prints verified candidates
- `AutoWork.exe status` — current /work pipeline state
- `AutoWork.exe doctor` — environment + transport health check (self-heals stale gates first)

## Discovery lanes (v2)

| Lane | Source | Status | Notes |
|---|---|---|---|
| `drushim` | drushim.co.il `__NEXT_DATA__` payload | **LIVE, primary** | 250+ rows/sweep: company, title, city, experience, scope, description, freshness |
| `ads` | AllJobs ad pages (CF-decoded CV mailboxes) | LIVE | in-ad mailboxes |
| `ak` | AllJobs employer-page dossiers | LIVE | 2 pages/keyword |
| `alljobs` | AllJobs guest search → employer sites | LIVE | |
| `recruiters` | standing recruiter channels (NETHR, Ethosia, Jobify360) | LIVE | skips channels marked filled (מלאה) |
| `jobclick`, `fbposts`, `linkedin`, `wave` | various | login-walled / rate-limited | manual `--lanes` only, fail to 0 rows gracefully |

Default rounds rotate the five live lanes; lanes harvest in parallel inside a round.

## Accuracy v2 (work-playbook fit rules)

Rejects: 3+ year experience mandates, team-lead/manager roles (Hebrew מנהל with
system-admin whitelist), filled positions (bare מלאה vs full-time משרה מלאה),
macOS-mandatory roles, security clearance. Prefers: hybrid/student/80%
positions, official `jobs@`-style mailboxes, fresh postings (היום / לפני X שעות).
Score gate: min_score 6. Sends are ordered by reply-probability tier
(official employer mailbox > active recruiter > open application), then score.

## Guarantees (the three NEVERs — unchanged, fail-closed)

NEVER an already-contacted place — contacted-index exact match; whole-employer
domain rule; sender-ledger exclusion set; live Gmail Sent-history re-check
immediately before every single send.

NEVER a fake place — verified official site (name-token match or employer-curated
link); mailbox published on that domain (Cloudflare-obfuscated emails XOR-decoded);
live DNS MX (8.8.8.8 + 1.1.1.1, fail-closed when unverifiable); free-mail rejected.

NEVER an irrelevant place — negative title filter + accuracy v2 rejects + role-family
match (devops, cloud, cyber, sysadmin, support) with score ≥ 6.

## Reliability (new in v2)

- **Gate self-heal**: a half-open completion gate from an interrupted $work session
  (older than `stale_gate_minutes`, default 30) is released automatically at doctor
  time; a FRESH gate is never touched (fail-closed).
- **UTF-8 everywhere**: every child process gets PYTHONIOENCODING/PYTHONUTF8 — the
  cp1252/Hebrew crash class is dead (regression-tested in `runs\_vtests\test_v2.py`).
- **Selftest fully green**: 38/38 checks, including re-anchored body-hash and an
  evolution-aware receipt validator.

## Ops

- Rebuild: `build-exe.cmd` (gates on py_compile + 35 offline vtests before PyInstaller).
- Offline battery: `runs\_vtests\test_v2.py`.
- Config: `auto-config.json` (caps: 15/run, 100/day; caches 15 min; send delay 15 s).
- Evidence per run: `runs\auto-<ts>\` (log, per-round lane snapshots, rejected reasons,
  `summary.json` with every send verdict, finalize receipt).

Built on the proven /work stack (`F:\backup\ai\work-skill`): work_pipeline.py,
Gmail connector, validate_lead.py, ledgers, and the completion-gate plugin.

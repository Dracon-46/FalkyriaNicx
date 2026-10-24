# Telemetry

Nicx offers **optional external usage analytics** so Falkyria can see
where the product breaks, what features people actually use, and how to
make it better. The legally binding text is the privacy policy bundled with
Nicx (`nicx legal privacidade`, or Settings → Privacidade in the app). This page documents exactly what is and isn't
collected, where the data goes, and how to enable or disable it.

## TL;DR

- **Off until you choose to share.** In an interactive Bash installation or
  `nicx init`, the dedicated prompt says: **Aperte Enter ou S para aceitar,
  ou N para recusar**. The desktop and browser app ask once on first launch.
  Enter or S enables sharing; EOF, cancellation, or an unattended run does not.
- **Installation ID** — one random UUID links install and usage events.
  A random identifier is not a guarantee of legal anonymity.
- **No chat content, ever.** Only counts, timings, and feature names.
- **Destination: Falkyria's Supabase project in São Paulo, Brazil** — only
  after consent; see below.
- **Retention: 24 months**, enforced by a nightly job on the server.
- **Right to deletion**: Settings → Privacidade → "Apagar meus dados" erases
  every event of this installation on the server.

## Choosing whether to share

The Bash installer asks before its first analytics beacon. The answer is
saved as `[analytics] enabled` in `config.toml`, so the backend and frontend
use the same choice. Installer reruns save the latest answer even when
completed installation steps are skipped. No IP-based country lookup is used;
the same prompt applies everywhere.

For unattended installs, consent explicitly with `--analytics` or decline with
`--no-analytics`:

```bash
curl -fsSL https://raw.githubusercontent.com/Dracon-46/FalkyriaNicx/main/scripts/install/install.sh | bash -s -- --analytics
# Or: ... | bash -s -- --no-analytics
nicx init --analytics
# Or: nicx init --no-analytics
```

To change your choice later:

```bash
nicx config set analytics.enabled false
# To enable: nicx config set analytics.enabled true
```

Restart the server and reload the frontend after changing the setting.
An existing, explicitly configured `enabled = true` remains enabled until
changed. Configurations without an analytics setting default to off.
Local performance telemetry is a separate setting.

Events are sent only when `enabled = true` and both `[analytics] host` and
`[analytics] key` are set. Nicx ships with Falkyria's destination as the
default, so consent alone decides; set `host = ""` to disable sending
entirely regardless of consent.

## What we collect

### Lifecycle events

| Event | Source | Why we send it |
|---|---|---|
| `install_started` | `install.sh` | Top of install funnel |
| `install_stage_completed` | `install.sh` | Per-stage timing — where do people drop off? |
| `install_completed` | `install.sh` | Did the install succeed? |
| `install_failed` | `install.sh` | Which stage failed, and on what OS |
| `app_opened` | Backend + frontend | DAU / WAU / MAU |
| `setup_completed` | Frontend | First-run wizard finished |
| `first_chat_sent` | Backend | First-ever message — activation |
| `uninstall_started` | `uninstall.sh` (if user runs it) | Churn signal |

### Usage events

| Event | Why we send it |
|---|---|
| `chat_session_ended` | Aggregated per-session: turn count, tokens, latency, tool count |
| `tool_first_used` | Which built-in tools are actually adopted |
| `model_changed` | How often users switch models |
| `feature_used` | Which features get traffic, which don't |
| `connector_auth_completed` | Which connectors people set up |
| `error_shown_to_user` | User-visible error class (not stack trace) |
| `feedback_submitted` | Was a rating given? Was a comment included? |
| `settings_changed` | Which settings get toggled |
| `usage_daily_summary` | Once-per-day aggregated counts |

The canonical, authoritative list with every property name and its
type validator lives in
[`src/nicx/privacidade/events.py`](../src/nicx/privacidade/events.py).
That file is the only place new events can be added — PR review is
the gate.

## Backend safeguards

Backend events use a property allowlist and value-level redaction:

- **Chat content** — prompts, model outputs, system messages, tool args.
- **File paths** — anything matching `~/`, `$HOME`, `/Users/<name>`, `/home/<name>`, `file://`.
- **Emails** matching the redaction patterns.
- **IP addresses** (IPv4 + IPv6) in property values. IP geolocation is
  disabled in the backend SDK; the receiving infrastructure can still
  observe connection IPs.
- **MAC addresses** matching the redaction patterns. Event properties do
  not include hardware serials or drive UUIDs.
- **Stack traces** — only error class enums.
- **API keys, OAuth tokens, JWTs, bearer tokens, password assignments** —
  matched and dropped at value level.
- **Hostnames** that look personal (e.g. `alice-macbook.local`).
- **Lists, dicts, sets** — composite values are never sent so PII can't
  smuggle through inside containers.

Two independent filters run before backend event properties are sent:

1. [`src/nicx/privacidade/redaction.py`](../src/nicx/privacidade/redaction.py) — value-level pattern matching (20+ regexes for PII).
2. [`src/nicx/privacidade/events.py`](../src/nicx/privacidade/events.py) — structural allowlist (event name + property name + type validator).

Any failure at either layer → the event or property is silently
dropped. Tests covering the patterns: [`tests/privacidade/test_redaction.py`](../tests/analytics/test_redaction.py).

The frontend never talks to the analytics destination directly: it posts
each event to the local backend (`POST /v1/analytics/capture`), which runs
it through the same two layers. Installer beacons use fixed fields
assembled separately.

## Where the data goes

- Events go to the `nicx_events` table of Falkyria's **Supabase** project
  (region `sa-east-1`, São Paulo), via its REST API. The schema, row level
  security and retention job live in `supabase/migrations/`.
- The app ships Supabase's **publishable** key. Row level security only lets
  it insert well-formed events: it cannot read, change or delete anything.
  Only Falkyria administrators with a confirmed email can read the data
  (the analytics dashboard in the app, "Painel Falkyria").
- The runtime reads `[analytics] host` and `[analytics] key` from
  `config.toml`; the installer reads `NICX_ANALYTICS_HOST` and
  `NICX_ANALYTICS_KEY` (set them to empty strings to disable).
- **Never** sold, shared with advertisers, or used for anything other
  than improving Nicx.

## Retention

- Events older than **24 months** are deleted every night by a `pg_cron`
  job on the server.
- "Apagar meus dados" (Settings → Privacidade, or `POST /v1/analytics/forget`)
  deletes every event of this installation on the server and then rotates the
  local installation ID.

## How identity works

A single UUID v4 is generated when sharing is first enabled and stored at
`~/.nicx/anon_id`. The install script, backend, and frontend all
read the same file so events across the lifecycle can be linked to the
same installation.

Deleting the file only changes the identifier used for future events; to
erase what was already sent, use "Apagar meus dados" first.

## For researchers and contributors

- **Adding an event**: edit `src/nicx/privacidade/events.py`,
  declare the spec, then update this page. PR review enforces both.
- **Adding a PII pattern**: edit `src/nicx/privacidade/redaction.py`
  and add a test case in `tests/privacidade/test_redaction.py`.
- **Inspecting what your install sends**: run with
  `NICX_LOG_LEVEL=DEBUG` and grep for `Analytics`. You'll see
  every event name and (redacted) property dict before it ships.

## Related

- Local telemetry (FLOPs, energy, latency stored in
  `~/.nicx/telemetry.db`) is a **separate** subsystem documented
  in [`src/nicx/registros/telemetria/`](../src/nicx/registros/telemetria/). It
  never leaves the machine and is controlled by `[telemetry]` (not
  `[analytics]`) in `config.toml`.

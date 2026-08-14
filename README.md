# buildpolaris_bff

**The backend / system-of-record for the BuildPolaris platform.**

`buildpolaris_bff` is a custom [Frappe](https://frappeframework.com) app that runs *inside* an [ERPNext v16](https://frappe.io/releases/version-16) site. It is not a standalone service — it is installed alongside ERPNext on the same bench/site, and it is the **only** place in the whole BuildPolaris platform where a fact is created. MariaDB (owned by this app, via Frappe) is the single system of record. Everything else in the platform — the offline PWA's local database and the AI sidecar's vector/graph store — is a disposable, rebuildable projection of what lives here.

This document covers the project structure (folder hierarchy), what each part does, how to run the project, and the technologies/tools/libraries it needs to run correctly.

---

## 0. Related BuildPolaris repositories

BuildPolaris is three separate repositories that together make up one platform. Link the other two here:

- `buildpolaris_pwa` (offline-first frontend): `https://github.com/mrhj26ali/buildpolaris_pwa`
- `buildpolaris_ai` (AI/RAG sidecar): `https://github.com/mrhj26ali/buildpolaris_ai`

---

## 1. Where this component sits in the platform

```
buildpolaris_pwa  ──(REST, session cookie, replay-on-reconnect)──▶  buildpolaris_bff  ◀──(private-network REST/MCP, scope-limited)──▶  buildpolaris_ai
   (offline PWA,                                                     (THIS REPO —                                                       (RAG sidecar,
    disposable local DB)                                                Frappe app on ERPNext v16,                                          disposable store)
                                                                          MariaDB = system of record)
```

- `buildpolaris_bff` never trusts a write from the PWA or a proposal from the AI sidecar as final — every write is re-validated against live permissions and business rules here before it's applied. That re-validation is what "system of record" means structurally, not just as a label.
- The AI sidecar is never in the synchronous critical path of a non-AI workflow. If it's down, every other screen in BuildPolaris keeps working.

## 2. Architecture style

**Pragmatic Frappe-native layered modular monolith** — one Frappe app, one module per bounded context, a strict three-layer split inside every module:

| Layer | Owns | Never contains |
|---|---|---|
| `api.py` (`@frappe.whitelist()`) | Role/permission checks, request-shape validation, calling exactly **one** `services/` function, shaping the response | Business logic, raw `frappe.db` queries |
| `services/*.py` | All business rules, cross-module orchestration (via other modules' service functions, never raw SQL) | HTTP concerns — must be callable from a script, scheduled job, or test with the same signature |
| `doctype/*/*.py` | Per-DocType invariants that must hold no matter what calls `.save()` | Orchestration, calls to other modules' services |

Not microservices, and not Hexagonal/Clean Architecture applied uniformly — Frappe's own `Document.as_dict()` plus field-level permissions already give most of what a DTO layer would provide. A narrow typed-contract layer (`shared/contracts/`) exists only for complex nested payloads and for everything crossing the boundary into `buildpolaris_ai`, where a language/process boundary makes an implicit dict contract a real risk.

## 3. Project structure (folder hierarchy)

```text
buildpolaris_bff/
│
├── pyproject.toml
├── requirements.txt
├── hooks.py                     # Frappe app hooks: DocType events, scheduled jobs
├── modules.txt
├── patches.txt
│
├── shared/                      # Cross-module primitives — no business logic
│   ├── erpnext_adapter.py       # Thin wrapper over ERPNext's own accounting/PO primitives
│   ├── offline_sync_service.py  # Re-validates & applies queued writes replayed from the PWA
│   ├── security_log.py
│   ├── crypto_utils.py
│   ├── api_envelope.py          # Standard response shape for every api.py endpoint
│   ├── idempotency.py           # Dedupes writes carrying an Idempotency-Key header
│   ├── permissions.py
│   ├── scope_assertion.py       # Mints the short-TTL signed scope token sent to buildpolaris_ai
│   ├── rate_limit.py
│   ├── exceptions.py
│   └── contracts/                # Typed request/response models — only for complex payloads
│       ├── copilot_contracts.py
│       ├── ingestion_contracts.py
│       ├── mcp_tool_contracts.py
│       └── approval_contracts.py
│
├── identity/                    # Users, roles, invitations, session lifecycle, change history
│   ├── api.py
│   ├── services/
│   └── doctype/account_activation_token/
│
├── scheduling/                  # WBS, critical-path scheduling, baselines, field look-ahead
│   ├── api.py
│   ├── services/
│   │   └── cpm/                 # Forward/backward pass, critical path, DCMA checks —
│   │                             #   the SAME algorithm the frontend runs client-side, golden-tested
│   └── doctype/                 # task_dependency, schedule_baseline, baseline_task_snapshot
│
├── financials/                  # Budget/cost codes, commitments, billing, change events, EVM
│   ├── api.py
│   ├── services/
│   └── doctype/                 # cost_code, commitment, change_event, pay_application(+line), evm_snapshot
│
├── communications/               # RFIs, submittals, transmittals, meetings, escalation
│   ├── api.py
│   ├── services/
│   └── doctype/                 # rfi(+watcher), submittal_package(+line), transmittal(+recipient/doc),
│                                 #   meeting_series, meeting_minutes, action_item
│
├── document_control/             # Drawings and drawing revisions
│   ├── api.py
│   ├── services/
│   └── doctype/                 # drawing, drawing_revision, drawing_annotation
│
├── field/                        # Daily logs, JSA, safety incidents, punch list
│   ├── api.py                    #   (the field DocTypes the frontend is allowed to write offline)
│   ├── services/
│   └── doctype/
│
├── closeout/                     # Substantial completion, lien waivers, closeout package
│   ├── api.py
│   ├── services/
│   └── doctype/
│
├── ai_copilot/                   # AI governance, ingestion triggers, MCP server host
│   ├── api.py
│   ├── services/                 # gateway, ingestion trigger, entity mirror, proposal/approval/execution, audit
│   ├── mcp/                      # buildpolaris_bff HOSTS the MCP server; buildpolaris_ai is the client
│   │   ├── mcp_server.py
│   │   ├── tool_registry.py
│   │   └── tools/                # scheduling_tools, financial_tools, communication_tools, field_tools
│   │                              #   — each a thin wrapper around the SAME services/ function a human screen calls
│   └── doctype/                  # ai_document_index, agent_action_approval, agent_mutation_log,
│                                  #   copilot_thread, copilot_message
```

**Why this shape, briefly:** every module is `api.py → services/ → doctype/`, always in that order — so "which module owns this" and "which folder does this code belong in" are always the same question. `ai_copilot/` is the one module that's structurally different: it's the only place the platform talks to the AI sidecar, and it's the only module that hosts an MCP server rather than just a REST `api.py`.

## 4. Technologies, tools & libraries

| Concern | Technology |
|---|---|
| Application framework | [Frappe Framework v16](https://frappe.io/framework/version-16) |
| ERP/base app | [ERPNext v16](https://frappe.io/releases/version-16) — provides accounting, roles/permissions, workspace, file/attachment handling, print/PDF, background jobs, and audit trail for free; this app extends it, never forks it |
| Language / runtime | Python **3.14+** (Frappe v16 requires it — older interpreters fail on syntax Frappe v16 itself uses) |
| Database | MariaDB — the platform's single system of record |
| Background jobs / cache | Redis + RQ, via `frappe.enqueue` (Frappe's own mechanism — no separate message broker) |
| Auth | Frappe's native session-cookie auth (`sid` cookie) for the frontend; a short-TTL signed scope assertion + service credential for calls to/from the AI sidecar — no custom JWT layer anywhere |
| Package/dependency mgmt | `pip` / `bench` (Frappe apps are installed and managed by `bench`, not a standalone `pip install`) |
| Lint / format | [Ruff](https://docs.astral.sh/ruff/) |
| Testing | `pytest`, plus Frappe's own native test runner (fixture auto-build from Link fields) |
| Real-time / streaming | Server-Sent Events proxy for the copilot response; ERPNext's own notification/`ToDo` engine handles everything else — no bespoke channel |

## 5. Prerequisites

- A Linux or macOS machine (or WSL on Windows) — Frappe/`bench` does not support native Windows
- Python **3.14+**
- Node.js, MariaDB, Redis, `yarn`, `wkhtmltopdf` — all installed automatically by the Frappe "Easy Install" script below, or manually if you're on a supported distro (see the install guide)
- `git`

## 6. Setup & installation — from zero to a running site

This app is **not** run on its own. It has to be installed into a Frappe bench, on the same site as ERPNext v16.

### Step 1 — Install ERPNext v16

Follow the official Frappe installation guide: **https://docs.frappe.io/framework/user/en/installation**

The short version (development setup, Linux/macOS/WSL):

```bash
# Installs bench, Python, Node, MariaDB, Redis, and all system dependencies
git clone https://github.com/frappe/bench ~/.bench
pip install -e ~/.bench --break-system-packages   # or follow the guide's Easy Install script

# Create a bench (this clones the frappe framework at version-16)
bench init --frappe-branch version-16 frappe-bench
cd frappe-bench

# Create a new site
bench new-site buildpolaris.local

# Get and install ERPNext v16 on that site
bench get-app --branch version-16 erpnext
bench --site buildpolaris.local install-app erpnext
```

You should now be able to run `bench start` and log into `http://buildpolaris.local:8000` with the Administrator account.

### Step 2 — Create the `buildpolaris_bff` custom app and install it on the same site

```bash
# From inside your frappe-bench directory:
bench new-app buildpolaris_bff
bench --site buildpolaris.local install-app buildpolaris_bff
```

This scaffolds an empty app under `frappe-bench/apps/buildpolaris_bff` and registers it on your site — installed **alongside** ERPNext, on the same site, not as a separate deployment.

### Step 3 — Replace the scaffold with this repository's code

```bash
cd apps/buildpolaris_bff
git init                                   # if not already a git repo
git remote add origin <this-repo-url>
git fetch origin
git checkout -f main                       # or whatever branch holds this codebase
```

(If your team clones this repo directly instead of scaffolding first, clone it straight into `frappe-bench/apps/buildpolaris_bff` and skip `bench new-app` — either path ends in the same place: this code living at `apps/buildpolaris_bff` inside the bench.)

### Step 4 — Install this app's dependencies and run migrations

```bash
cd ~/frappe-bench
bench setup requirements                  # installs this app's Python deps into the bench's env
bench --site buildpolaris.local migrate   # creates every DocType this app defines in MariaDB
```

### Step 5 — Run it

```bash
bench start
```

`buildpolaris_bff` is now set up — its DocTypes, `api.py` endpoints, and background jobs are live on the same site as ERPNext v16, sharing the same MariaDB database, the same Redis/RQ queues, and the same permission system.

## 7. Common commands during development

```bash
bench --site buildpolaris.local migrate        # after any DocType/schema change
bench --site buildpolaris.local console        # interactive Python shell with frappe bootstrapped
bench --site buildpolaris.local run-tests --app buildpolaris_bff
ruff check .                                   # lint
bench build                                    # rebuild frontend assets if a .js controller changed
```

## 8. Configuration

Secrets (DB credentials, backup encryption key, service credentials for the AI sidecar) live in Frappe's own `site_config.json` (encrypted at rest) — never in a `.env` file or committed anywhere.

## 9. No large pretrained models or bulk training data

This repository contains no pretrained models, embeddings, or bulk datasets — it's a Frappe application (Python source + DocType definitions) only. Model/embedding assets used by the platform live in and are documented by `buildpolaris_ai`.

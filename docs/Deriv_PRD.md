# Product Requirements Document
## Customer Support AI Evaluation Pipeline

**Version:** 1.0  
**Language:** Python  
**LLM Provider:** Anthropic (Claude)  
**Status:** Ready for Implementation

---

## Table of Contents

1. [Overview](#1-overview)
2. [Goals & Non-Goals](#2-goals--non-goals)
3. [Architecture Overview](#3-architecture-overview)
4. [Directory Structure](#4-directory-structure)
5. [Environment & Configuration](#5-environment--configuration)
6. [Pipeline Stages](#6-pipeline-stages)
7. [Input Specification](#7-input-specification)
8. [Output Artifacts](#8-output-artifacts)
9. [LLM Configuration](#9-llm-configuration)
10. [Error Handling](#10-error-handling)
11. [Human Override Checkpoint](#11-human-override-checkpoint)
12. [Deterministic Scoring Formula](#12-deterministic-scoring-formula)
13. [Validation Requirements](#13-validation-requirements)
14. [Optional Features in Scope](#14-optional-features-in-scope)
15. [Functional Requirements](#15-functional-requirements)
16. [Non-Functional Requirements](#16-non-functional-requirements)
17. [Acceptance Criteria](#17-acceptance-criteria)

---

## 1. Overview

This pipeline ingests customer support tickets and policy constraints from disk, generates AI draft replies, evaluates them through deterministic and LLM-based checks, pauses for a human override checkpoint, and produces a final routing recommendation report distinguishing which tickets are safe to auto-send versus which require human review.

The system is designed for **repeatability, auditability, and clear separation of concerns** between generation, evaluation, and decision-making. It is not a one-shot text generator — it is a staged, stateful engineering pipeline.

---

## 2. Goals & Non-Goals

### Goals
- Load and validate tickets and policy from disk on every run
- Generate one AI draft reply per ticket using Claude
- Enforce deterministic policy checks in Python code before any final decision
- Conduct a separate structured LLM review stage per ticket
- Support an interactive human override checkpoint
- Produce a final routing decision per ticket with explicit reasoning
- Log every LLM call with full metadata to `llm_calls.jsonl`
- Generate a human-readable evaluation report in Markdown
- Compute aggregate metrics deterministically in code
- Implement a repair/retry stage for replies that fail deterministic checks
- Be fully re-runnable from a clean checkout with no precomputed artifacts

### Non-Goals
- A web UI or REST API
- Multi-tenant or multi-user support
- Streaming LLM responses
- Prompt variant comparison (STRETCH — out of scope for this version)
- Persistent database storage
- Authentication or authorization

---

## 3. Architecture Overview

```
tickets.json + policy.json
        │
        ▼
┌─────────────────────┐
│   Stage 0: INIT     │  Load & validate inputs from disk
│   → INPUTS_LOADED   │  Write normalized_tickets.json
└────────┬────────────┘
         │
         ▼
┌──────────────────────────────┐
│  Stage 1: DRAFT GENERATION   │  1 LLM call per ticket (claude-haiku)
│  → DRAFT_REPLIES_GENERATED   │  Write draft_replies.json
└────────┬─────────────────────┘
         │
         ▼
┌────────────────────────────────────┐
│  Stage 2: DETERMINISTIC CHECKS     │  Pure Python, no LLM
│  → DETERMINISTIC_CHECKS_COMPLETE   │  Write policy_checks.json
└────────┬───────────────────────────┘
         │
         ├──── [If any ticket fails checks] ──────────────────┐
         │                                                     ▼
         │                                        ┌───────────────────────┐
         │                                        │  Stage 2b: REPAIR     │
         │                                        │  1 LLM call per fail  │
         │                                        │  Write repaired_replies.json
         │                                        └───────────┬───────────┘
         │                                                    │
         └────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────┐
│  Stage 3: LLM REVIEW     │  1 LLM call per ticket (separate from generation)
│  → LLM_REVIEW_COMPLETE   │  Write llm_review.json
└────────┬─────────────────┘
         │
         ▼
┌────────────────────────────────┐
│  Stage 4: HUMAN OVERRIDE       │  Interactive terminal prompt
│  → HUMAN_OVERRIDE_COMPLETE     │  Write human_overrides.json
└────────┬───────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│  Stage 5: FINAL ROUTING      │  Pure Python routing logic
│  → FINAL_ROUTING_DECIDED     │  Write final_decisions.json
└────────┬─────────────────────┘
         │
         ▼
┌──────────────────────────────┐
│  Stage 6: REPORT + METRICS   │  Deterministic aggregation
│  → REPORT_GENERATED          │  Write evaluation_report.md + metrics.json
└────────┬─────────────────────┘
         │
         ▼
┌─────────────────────────────┐
│  Stage 7: VALIDATION        │  validate.py checks all artifacts
│  → RESULTS_FINALISED        │
└─────────────────────────────┘
```

### Key Architectural Constraints
- Each stage reads from and writes to disk — no in-memory-only chains
- Generation and review are **never combined** into a single LLM call
- All routing logic lives in Python — the LLM only advises, never decides
- Human overrides are applied **before** `final_decisions.json` is written
- The pipeline fails fast on any LLM call error — no silent fallbacks

---

## 4. Directory Structure

```
project-root/
│
├── .agents/
│   └── rules/
│       ├── 00_overview.md          # Architecture + current phase
│       ├── 01_coding_standards.md  # Python conventions
│       ├── 02_stage_rules.md       # Per-stage implementation rules
│       ├── 03_llm_rules.md         # LLM call contracts
│       └── 04_artifact_schema.md   # JSON schema definitions
│
├── src/
│   ├── pipeline.py                 # Entrypoint — orchestrates all stages
│   ├── stages/
│   │   ├── __init__.py
│   │   ├── s0_load.py              # Input loading & validation
│   │   ├── s1_generate.py          # Draft reply generation
│   │   ├── s2_check.py             # Deterministic policy checks
│   │   ├── s2b_repair.py           # Repair stage (optional retry)
│   │   ├── s3_review.py            # LLM review stage
│   │   ├── s4_override.py          # Human override checkpoint
│   │   ├── s5_route.py             # Final routing logic
│   │   └── s6_report.py            # Report + metrics generation
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── client.py               # Anthropic client wrapper
│   │   └── logger.py               # llm_calls.jsonl logger
│   └── utils/
│       ├── __init__.py
│       └── state.py                # Pipeline state enum + tracker
│
├── outputs/                        # All generated artifacts written here
│   ├── normalized_tickets.json
│   ├── draft_replies.json
│   ├── policy_checks.json
│   ├── repaired_replies.json
│   ├── llm_review.json
│   ├── human_overrides.json
│   ├── final_decisions.json
│   ├── evaluation_report.md
│   └── metrics.json
│
├── logs/
│   └── llm_calls.jsonl             # Append-only LLM call log
│
├── tickets.json                    # Input — replaceable by evaluator
├── policy.json                     # Input — replaceable by evaluator
├── validate.py                     # Validation script
├── requirements.txt
├── .env.example
├── .env                            # Git-ignored
└── README.md
```

---

## 5. Environment & Configuration

### `.env` file (required, never committed)
```
ANTHROPIC_API_KEY=sk-ant-...
```

### `.env.example` (committed)
```
ANTHROPIC_API_KEY=your_key_here
```

### Config constants (`src/utils/state.py` or top of `pipeline.py`)
```python
GENERATION_MODEL = "claude-haiku-4-5"       # Most recent Haiku
REVIEW_MODEL     = "claude-haiku-4-5"
MAX_TOKENS       = 1024
TICKETS_PATH     = "tickets.json"
POLICY_PATH      = "policy.json"
OUTPUTS_DIR      = "outputs/"
LOGS_DIR         = "logs/"
NON_INTERACTIVE  = False  # Set to True via --no-interactive flag
```

### CLI Flags
```bash
python src/pipeline.py                     # Default: interactive mode
python src/pipeline.py --no-interactive    # Skip human override prompt
```

The `--no-interactive` flag must still write `human_overrides.json` with an empty overrides list and a note that the flag was used.

---

## 6. Pipeline Stages

### State Enum
```python
from enum import Enum, auto

class PipelineState(Enum):
    INIT = auto()
    INPUTS_LOADED = auto()
    DRAFT_REPLIES_GENERATED = auto()
    DETERMINISTIC_CHECKS_COMPLETE = auto()
    LLM_REVIEW_COMPLETE = auto()
    HUMAN_OVERRIDE_COMPLETE = auto()
    FINAL_ROUTING_DECIDED = auto()
    REPORT_GENERATED = auto()
    VALIDATION_COMPLETE = auto()
    RESULTS_FINALISED = auto()
```

Each stage function must:
1. Accept current state and validate it is the expected predecessor state
2. Do its work
3. Write its artifact(s) to `outputs/`
4. Return the next state

---

## 7. Input Specification

### `tickets.json`
Array of ticket objects. Each must contain:

| Field | Type | Required |
|---|---|---|
| `ticket_id` | string | yes |
| `customer_tone` | string | yes |
| `issue_type` | string | yes (must be in policy allowed list) |
| `customer_message` | string | yes |
| `account_context` | object | yes (can contain nulls) |

### `policy.json`
Object containing:

| Field | Type | Required |
|---|---|---|
| `allowed_issue_types` | string[] | yes |
| `required_reply_sections` | string[] | yes |
| `forbidden_claims` | string[] | yes |
| `routing_rules` | object | yes |
| `quality_rubric` | object (keys 1–5) | yes |

### Validation failures
If input validation fails, the pipeline must print a clear error message identifying which field/ticket failed and exit with code 1.

---

## 8. Output Artifacts

### `normalized_tickets.json`
The validated, normalized array of tickets. Same schema as input but guarantees all fields are present and types are correct.

### `draft_replies.json`
```json
[
  {
    "ticket_id": "string",
    "reply_text": "string",
    "reply_sections_present": ["acknowledgement", "next_steps", "safety_note"]
  }
]
```
`reply_sections_present` is computed by string matching in Python — not extracted from the LLM response.

### `policy_checks.json`
```json
[
  {
    "ticket_id": "string",
    "passed": true,
    "failed_checks": [],
    "must_human_review": false,
    "deterministic_score": 95
  }
]
```

### `repaired_replies.json`
```json
[
  {
    "ticket_id": "string",
    "original_reply_text": "string",
    "repaired_reply_text": "string",
    "repair_attempted": true,
    "repair_resolved_checks": ["check_name"],
    "still_failed_checks": ["check_name"]
  }
]
```
Only tickets that failed deterministic checks have entries here.

### `llm_review.json`
```json
[
  {
    "ticket_id": "string",
    "quality_rating": 4,
    "policy_risk": "low",
    "review_summary": "string",
    "suggested_fix": "string"
  }
]
```
`policy_risk` must be one of: `low`, `medium`, `high`. No other values accepted.

### `human_overrides.json`
```json
{
  "overrides": [
    {
      "ticket_id": "string",
      "override_route": "auto_send | human_review",
      "operator_input": "raw string entered by operator"
    }
  ],
  "non_interactive_mode": false
}
```

### `final_decisions.json`
```json
[
  {
    "ticket_id": "string",
    "draft_reply": "string",
    "deterministic_passed": true,
    "quality_rating": 4,
    "policy_risk": "low",
    "initial_route": "auto_send",
    "final_route": "human_review",
    "decision_reason": "string"
  }
]
```

### `evaluation_report.md`
Must contain these sections (in order):
- `## Summary`
- `## Auto-send Candidates`
- `## Human Review Required`
- `## Common Failure Patterns`
- `## Improvement Suggestions`

Each ticket entry must include one sentence of ticket-specific reasoning.

### `metrics.json`
```json
{
  "total_tickets": 4,
  "auto_send_count": 1,
  "human_review_count": 3,
  "deterministic_pass_rate": 0.75,
  "average_quality_rating": 3.5,
  "repair_attempted_count": 1,
  "repair_success_count": 0
}
```
All values computed in Python. `average_quality_rating` is the mean of `quality_rating` from `llm_review.json`.

### `llm_calls.jsonl`
Append-only. One JSON object per line per LLM call:
```json
{
  "stage": "draft_generation",
  "ticket_id": "T-1001",
  "timestamp": "2025-01-01T12:00:00Z",
  "provider": "anthropic",
  "model": "claude-haiku-4-5",
  "prompt_hash": "sha256:...",
  "input_artifacts": ["tickets.json", "policy.json"],
  "output_artifact": "outputs/draft_replies.json"
}
```
Valid `stage` values: `draft_generation`, `llm_review`, `repair`

---

## 9. LLM Configuration

### Model
`claude-haiku-4-5` for both generation and review stages. This resolves to the most recent Haiku model at time of implementation.

### Call Contract
- Every call uses `anthropic.Anthropic()` client (loaded via `python-dotenv`)
- `max_tokens`: 1024
- No streaming
- No batching — each ticket is a separate API call
- Temperature: default (not set explicitly, let the model use its default)

### Prompt Structure — Draft Generation
```
System: You are a professional customer support agent. You must follow the policy constraints provided. Never make forbidden claims. Always include all required reply sections.

User:
Ticket: {ticket_json}
Account Context: {account_context_json}
Policy - Required sections: {required_reply_sections}
Policy - Forbidden claims: {forbidden_claims}

Write a support reply that includes: {required_reply_sections}.
Do not: {forbidden_claims}.
Do not ask for the customer's full password.
Do not make promises about timelines or account approvals you cannot guarantee.
```

### Prompt Structure — LLM Review
```
System: You are a strict quality reviewer for a customer support AI system.

User:
Original Ticket: {ticket_json}
Draft Reply: {draft_reply_text}
Policy Constraints: {policy_json}
Deterministic Check Results: {policy_check_json}
Quality Rubric: {quality_rubric}

Respond in JSON only with this exact schema:
{
  "quality_rating": <integer 1-5>,
  "policy_risk": "<low|medium|high>",
  "review_summary": "<string>",
  "suggested_fix": "<string>"
}
```

### Prompt Structure — Repair
```
System: You are a customer support agent. You are revising a draft reply that failed policy checks.

User:
Original Ticket: {ticket_json}
Original Reply: {original_reply}
Failed Checks: {failed_checks}
Policy - Required sections: {required_reply_sections}
Policy - Forbidden claims: {forbidden_claims}

Rewrite the reply to fix the following issues: {failed_checks}.
```

---

## 10. Error Handling

### Strategy: Fail Fast
If any LLM call returns a non-200 response, raises an exception, or returns an unparseable response, the pipeline must:
1. Print a clear error message to stderr: `[PIPELINE ERROR] Stage: {stage}, Ticket: {ticket_id}, Error: {message}`
2. Exit with code 1 immediately
3. Not write partial artifacts for the failed stage

### JSON Parsing for LLM Review
The LLM review stage expects JSON output. If the response is not valid JSON:
1. Log the raw response to stderr
2. Fail fast with exit code 1

### Input File Missing
If `tickets.json` or `policy.json` does not exist at startup, print a clear error and exit code 1 before any LLM call is made.

---

## 11. Human Override Checkpoint

### Interactive Mode (default)
Before writing `final_decisions.json`, the pipeline prints a summary table to the terminal:

```
──────────────────────────────────────────────────────────────────────
 Ticket    │ Det. Check │ Quality │ Policy Risk │ Initial Route
──────────────────────────────────────────────────────────────────────
 T-1001    │ PASS       │ 4       │ low         │ auto_send
 T-1002    │ PASS       │ 3       │ low         │ auto_send
 T-1003    │ FAIL       │ 2       │ medium      │ human_review
 T-1004    │ PASS       │ 3       │ high        │ human_review
──────────────────────────────────────────────────────────────────────

Enter any ticket overrides as: <ticket_id> <auto_send|human_review>
Press Enter on an empty line to continue.
> 
```

The operator may enter zero or more overrides, one per line. Each line is validated — unrecognized ticket IDs or invalid routes print a warning and are ignored (not a fatal error).

### Non-Interactive Mode (`--no-interactive`)
Skip the prompt entirely. Write `human_overrides.json` with `"overrides": []` and `"non_interactive_mode": true`.

---

## 12. Deterministic Scoring Formula

Each check has a weight. The `deterministic_score` starts at 100 and deducts points per failed check:

| Check | Deduction |
|---|---|
| All required sections present | -30 |
| No full password request | -25 |
| No guaranteed timeline | -20 |
| No unsupported funds-released claim | -15 |
| No blaming/dismissive language | -10 |

`deterministic_score` = 100 − (sum of deductions for failed checks)  
Minimum score is 0.

`passed` = True if `deterministic_score == 100`  
`must_human_review` = True if `passed == False` OR `customer_tone == "angry"` OR `issue_type == "bonus_dispute"`

---

## 13. Validation Requirements

`validate.py` must check and report on all of the following:

| Check | Pass Condition |
|---|---|
| All required artifacts exist | File present in `outputs/` or project root |
| All JSON files parse cleanly | No JSON decode errors |
| `tickets.json` was read from disk | Confirmed via normalized_tickets.json matching |
| One generation call per ticket | `llm_calls.jsonl` has N `draft_generation` records for N tickets |
| One review call per ticket | `llm_calls.jsonl` has N `llm_review` records |
| Generation and review are separate | No single record has both stage values |
| `reply_sections_present` is present | Key exists in every `draft_replies.json` entry |
| `policy_risk` values are valid | Only `low`, `medium`, `high` appear |
| Final routing reflects rules | All angry/bonus_dispute/failed-check tickets are `human_review` unless explicitly overridden |
| `evaluation_report.md` has required sections | All 5 section headers present |
| `llm_calls.jsonl` has separate stage records | Both `draft_generation` and `llm_review` stages present |

`validate.py` exits with code 0 if all checks pass, code 1 if any fail, printing a per-check status.

---

## 14. Optional Features in Scope

### Repair / Retry Stage (SHOULD)
- Triggered automatically after deterministic checks for any ticket that fails
- One additional LLM call per failed ticket using the repair prompt
- Re-runs deterministic checks on the repaired reply
- If repair passes: `repaired_replies.json` reflects resolved checks, but `policy_checks.json` retains the **original failure**
- The final routing still considers the original failure signal; repair is informational only
- Repair calls are logged to `llm_calls.jsonl` with `"stage": "repair"`

### Metrics Summary (SHOULD)
- `metrics.json` is always written as the last step before validation
- All aggregations are pure Python (`sum`, `len`, division)
- `average_quality_rating` is `sum(ratings) / len(ratings)` rounded to 2 decimal places
- `deterministic_pass_rate` is `pass_count / total_tickets`

---

## 15. Functional Requirements

| ID | Requirement |
|---|---|
| FR-01 | Pipeline reads tickets and policy from disk on every run |
| FR-02 | Input validation rejects missing required fields with exit code 1 |
| FR-03 | One LLM call per ticket for draft generation — no batching |
| FR-04 | `reply_sections_present` computed by Python string matching, not the model |
| FR-05 | Deterministic checks run in Python before any final routing decision |
| FR-06 | `deterministic_score` computed via the defined formula |
| FR-07 | LLM review is a separate call from generation per ticket |
| FR-08 | LLM review prompt includes rubric, policy, deterministic check results |
| FR-09 | `policy_risk` constrained to `low`, `medium`, `high` only |
| FR-10 | Human override checkpoint runs before `final_decisions.json` is written |
| FR-11 | Operator overrides are applied to final routing |
| FR-12 | `--no-interactive` flag skips the checkpoint and writes empty overrides |
| FR-13 | Routing rules are hard-coded in Python (angry → human_review, bonus_dispute → human_review, failed checks → human_review) |
| FR-14 | Every LLM call is logged to `llm_calls.jsonl` with required fields |
| FR-15 | `prompt_hash` is SHA-256 of the full prompt string |
| FR-16 | `evaluation_report.md` contains all 5 required sections |
| FR-17 | `metrics.json` is computed deterministically in code |
| FR-18 | Repair stage triggers automatically for failed deterministic checks |
| FR-19 | Original failure signal is preserved after repair |
| FR-20 | `validate.py` exits 0 on success, 1 on any failure |

---

## 16. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-01 | Pipeline is fully re-runnable from clean checkout |
| NFR-02 | No precomputed / static artifacts committed to repo |
| NFR-03 | API key loaded from `.env` only — never hardcoded |
| NFR-04 | Fail fast on LLM errors — no silent fallback |
| NFR-05 | All outputs written to `outputs/` directory |
| NFR-06 | All LLM logs written to `logs/llm_calls.jsonl` |
| NFR-07 | Code is modular — one file per stage under `src/stages/` |
| NFR-08 | Python 3.10+ compatible |
| NFR-09 | `requirements.txt` pins all dependencies |
| NFR-10 | `.env` is git-ignored; `.env.example` is committed |

---

## 17. Acceptance Criteria

The pipeline is considered complete when:

1. `python src/pipeline.py` runs end-to-end from a clean checkout with only `tickets.json`, `policy.json`, and a valid `.env`
2. All required artifacts are generated in `outputs/` and `logs/`
3. `python validate.py` exits with code 0
4. Replacing `tickets.json` with different fixture data causes the pipeline to re-run correctly without code changes
5. The `--no-interactive` flag produces a valid run with empty overrides
6. A manual override in interactive mode changes the corresponding ticket's `final_route` in `final_decisions.json`
7. Introducing a forbidden phrase into a generated reply causes that ticket to fail deterministic checks and route to `human_review`
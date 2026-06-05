# Customer Support AI Evaluation Pipeline

An automated, stateful Python pipeline that ingests customer support tickets and policy constraints, generates draft replies using the Anthropic API, performs deterministic compliance checks and structured LLM reviews, processes human override checkpoints, and generates routing decisions and reports.

## Architecture & Stages

The pipeline follows a stateful staging architecture:
1. **Stage 0: INIT / INPUTS_LOADED** - Load & validate inputs (`tickets.json`, `policy.json`) from disk.
2. **Stage 1: DRAFT_REPLIES_GENERATED** - Generate draft replies using `claude-haiku-4-5`.
3. **Stage 2: DETERMINISTIC_CHECKS_COMPLETE** - Run rule-based policy validation in pure Python.
   - **Stage 2b: REPAIR** - (Optional) Attempt LLM-based repair on failed draft replies.
4. **Stage 3: LLM_REVIEW_COMPLETE** - Structure review of replies against the policy rubric using LLM.
5. **Stage 4: HUMAN_OVERRIDE_COMPLETE** - CLI prompt for operator review and manual override.
6. **Stage 5: FINAL_ROUTING_DECIDED** - Apply routing rules and overrides to decide final ticket paths.
7. **Stage 6: REPORT_GENERATED** - Compile performance metrics and build the `evaluation_report.md`.
8. **Stage 7: VALIDATION_COMPLETE / RESULTS_FINALISED** - Verify output artifacts integrity using `validate.py`.

---

## Directory Layout

```text
project-root/
│
├── .agents/
│   └── rules/                      # Agent behavior rules (overview, coding standards, etc.)
│
├── src/
│   ├── pipeline.py                 # Pipeline Orchestrator & CLI Entrypoint
│   ├── stages/                     # Individual modular pipeline stages
│   │   ├── s0_load.py
│   │   ├── s1_generate.py
│   │   ├── s2_check.py
│   │   ├── s2b_repair.py
│   │   ├── s3_review.py
│   │   ├── s4_override.py
│   │   ├── s5_route.py
│   │   └── s6_report.py
│   │
│   ├── llm/                        # LLM communication wrapper & log logger
│   │   ├── client.py
│   │   └── logger.py
│   │
│   └── utils/
│       └── state.py                # Pipeline states enum and configurations
│
├── outputs/                        # Output directory for execution artifacts
├── logs/                           # Append-only logs (llm_calls.jsonl)
├── requirements.txt                # pinned python dependencies
├── .env.example                    # Example configuration file
└── README.md                       # Project overview and instructions
```

---

## Setup & Installation

1. **Clone & Navigate:**
   ```bash
   cd Deriv-Technical
   ```

2. **Set up Virtual Environment:**
   ```bash
   python -m venv .venv
   # Windows:
   .venv\Scripts\activate
   # macOS/Linux:
   source .venv/bin/activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables Configuration:**
   Copy `.env.example` to `.env` and fill in your Anthropic API Key:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` to include:
   ```env
   ANTHROPIC_API_KEY=your_actual_api_key_here
   ```

---

## Usage

Run the pipeline using Python:

```bash
# Default interactive mode (prompts for operator override on Stage 4)
python src/pipeline.py

# Non-interactive mode (skips operator override and defaults to initial routing)
python src/pipeline.py --no-interactive
```

---

## Output Artifacts & Logs

All results will be written under the `outputs/` folder, and LLM call histories will be appended to `logs/llm_calls.jsonl`.

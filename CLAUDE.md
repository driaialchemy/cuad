# CUAD Contract Review & Risk Flagging Pipeline

## What This Project Does

This project implements a production-grade asynchronous multi-agent pipeline that ingests real CUAD (Contract Understanding Atticus Dataset) contracts, extracts key legal clauses using pre-labeled ground-truth answers, compares them against a standard legal playbook, flags risk deviations with severity ratings, and produces a human-readable audit log per contract.

The pipeline demonstrates both business impact (risk flagging and recommendations) and output validation (ground-truth answers from CUAD for independent verification).

## Dataset Location and Format

- **Source**: `C:\Users\msell\OneDrive\AIAlchemy\cuaddataset\data.zip`
- **File inside zip**: `CUADv1.json`
- **Format**: SQuAD-style JSON with top-level key `"data"` containing a list of contracts
- Each contract has `"title"` and `"paragraphs"` (with `"context"` and `"qas"`)
- Each QA has `"question"`, `"id"`, `"is_impossible"`, and `"answers"`

## Installation

```bash
pip install -r requirements.txt
```

## Running the Pipeline

Run on a specific contract by title:

```bash
python main.py --contract "LIMEENERGYCO_09_09_1999-EX-10-DISTRIBUTOR AGREEMENT"
```

Run on the first contract in the dataset:

```bash
python main.py --first
```

## Testing

```bash
pytest tests/ -v
```

## Three-Agent Pipeline

1. **ExtractionAgent** — Parses CUAD JSON from the zip archive, finds the target contract, extracts clause spans from pre-labeled Q&A pairs, and filters to the 10 playbook clause categories.

2. **RiskAgent** — Compares extracted clauses against `data/playbook.json` standards, assigns severity ratings (critical/high/medium/low/none), and produces a risk summary with overall severity.

3. **SummaryAgent** — Produces a plain-English executive risk brief with clause-by-clause breakdown, top priority actions, and a structured final report.

The **Orchestrator** (`src/orchestrator/engine.py`) routes the shared `AgentState` through each agent in sequence, halts on errors, and exports an `EXECUTION_LOG.md` audit trail.

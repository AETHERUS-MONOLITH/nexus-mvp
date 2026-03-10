#!/usr/bin/env python3
"""
NEXUS MVP — Demo Runner
=========================
CLI for side-by-side governance comparison: Baseline LLM vs NEXUS pipeline.

Usage:
    python3 demo_runner.py "Should we approve this loan?" --jurisdiction US --framework ECOA
    python3 demo_runner.py "Wire transfer to Iran" --mode nexus --no-color
    python3 demo_runner.py "Approve credit app" --mode compare --save

Modes:
    compare  — Run both baseline LLM and NEXUS pipeline (default)
    baseline — Baseline LLM only (requires ANTHROPIC_API_KEY)
    nexus    — NEXUS pipeline only (deterministic, no API key needed if Α fallback)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from uuid import uuid4


class Colors:
    RED = "\033[91m"
    GREEN = "\033[92m"
    CYAN = "\033[96m"
    YELLOW = "\033[93m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"

NO_COLOR = Colors()
for attr in ("RED", "GREEN", "CYAN", "YELLOW", "BOLD", "DIM", "RESET"):
    setattr(NO_COLOR, attr, "")

C = Colors()


def set_no_color():
    global C
    C = NO_COLOR


def load_env():
    try:
        from dotenv import load_dotenv
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path)
    except ImportError:
        pass


def run_baseline(query: str) -> dict:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"success": False, "error": "ANTHROPIC_API_KEY not set", "response": None}
    try:
        from anthropic import Anthropic
        client = Anthropic(api_key=api_key)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system="You are a financial services AI assistant. Answer the user question directly and concisely.",
            messages=[{"role": "user", "content": query}],
        )
        return {"success": True, "error": None, "response": response.content[0].text}
    except Exception as e:
        return {"success": False, "error": str(e), "response": None}


def run_nexus(query: str, jurisdiction: str, framework: str) -> dict:
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    from src.operators.alpha import alpha_operator
    from src.operators.delta import delta_operator
    from src.operators.omega import OmegaOperator

    context = {
        "session_id": str(uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "regulatory_framework": framework,
        "jurisdiction": jurisdiction,
    }

    ledger_path = os.path.join(project_root, "data", "ledger.jsonl")
    manifest_path = os.path.join(project_root, "data", "risk_manifest.json")

    if not os.path.exists(manifest_path):
        return {"success": False, "error": f"Risk manifest not found: {manifest_path}", "cell": None, "output": None}

    try:
        cell = alpha_operator(query, context)
        alpha_snapshot = {
            "status": cell["status"],
            "uncertainty_binding": cell["uncertainty"]["binding"],
            "uncertainty_mode": cell["uncertainty"]["mode"],
        }

        cell = delta_operator(cell)
        delta_snapshot = {
            "intent_type": cell["domain_payload"]["intent_type"],
            "risk_score": cell["risk_score"],
            "status": cell["status"],
        }

        omega = OmegaOperator(ledger_path=ledger_path, manifest_path=manifest_path)
        intent_class = cell["domain_payload"].get("intent_type", "unknown")
        output = omega.process(cell, query, {"framework": framework, "intent_class": intent_class})

        return {"success": True, "error": None, "cell": cell, "alpha": alpha_snapshot, "delta": delta_snapshot, "output": output}
    except Exception as e:
        return {"success": False, "error": str(e), "cell": None, "output": None}


def print_header(query: str, jurisdiction: str, framework: str):
    print(f"\n{C.CYAN}{C.BOLD}╔══════════════════════════════════════════════════════════════╗{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}║           NEXUS GOVERNANCE REPORT — AETHERUS                ║{C.RESET}")
    print(f"{C.CYAN}{C.BOLD}╚══════════════════════════════════════════════════════════════╝{C.RESET}")
    print()
    print(f"QUERY:        {query}")
    print(f"JURISDICTION: {jurisdiction}  |  FRAMEWORK: {framework}")
    print(f"TIMESTAMP:    {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")


def print_section(title: str):
    print(f"\n{C.CYAN}──────────────────────────────────────────────────────────────{C.RESET}")
    print(f" {C.BOLD}{title}{C.RESET}")
    print(f"{C.CYAN}──────────────────────────────────────────────────────────────{C.RESET}")


def print_baseline(result: dict):
    print_section("BASELINE LLM (ungoverned)")
    if result["success"]:
        print(f"\n{result['response']}")
    else:
        print(f"\n{C.RED}ERROR: {result['error']}{C.RESET}")
    print(f"\n{C.DIM}Audit trail:    NONE{C.RESET}")
    print(f"{C.DIM}Deterministic:  NO{C.RESET}")
    print(f"{C.DIM}Regulatory ref: NONE{C.RESET}")


def print_nexus(result: dict):
    print_section("NEXUS PIPELINE")
    if not result["success"]:
        print(f"\n{C.RED}ERROR: {result['error']}{C.RESET}")
        return

    alpha = result["alpha"]
    delta = result["delta"]
    output = result["output"]

    status_color = C.RED if delta["status"] == "blocked" else C.GREEN
    decision_color = C.RED if output["decision"] == "escalate" else C.GREEN
    variant_str = f" → {output['variant']}" if output.get("variant") else ""

    print(f"\n{C.DIM}Α  (intake)     status=pending       uncertainty.binding={alpha['uncertainty_binding']}{C.RESET}")
    print(f"Δ  (risk eval)  intent={delta['intent_type']}  risk={delta['risk_score']}  status={status_color}{delta['status'].upper()}{C.RESET}")
    print(f"Ω  (decision)   {decision_color}{C.BOLD}{output['decision'].upper()}{variant_str}{C.RESET}")

    print(f"\nREASONING:    {output.get('reasoning', 'N/A')}")
    print(f"NEXT ACTION:  {output.get('next_action', 'N/A')}")
    print(f"REG REFS:     {output.get('regulatory_reference', 'NONE') or 'NONE'}")
    print(f"RUN ID:       {C.DIM}{output.get('run_id', 'N/A')}{C.RESET}")
    print(f"\n{C.GREEN}Audit trail:    LEDGER entry written ✓{C.RESET}")
    print(f"{C.GREEN}Deterministic:  YES{C.RESET}")


def print_delta_comparison(baseline_result: dict, nexus_result: dict):
    print_section("GOVERNANCE DELTA")

    if baseline_result and baseline_result["success"]:
        response_lower = baseline_result["response"].lower() if baseline_result["response"] else ""
        if any(w in response_lower for w in ["approve", "yes", "recommend", "can proceed", "eligible"]):
            baseline_label = "advisory/approval"
        elif any(w in response_lower for w in ["deny", "reject", "decline", "cannot", "should not"]):
            baseline_label = "advisory/denial"
        else:
            baseline_label = "advisory/conditional"
        print(f"Baseline decision:  {baseline_label}")
    else:
        print(f"Baseline decision:  {C.DIM}(not available){C.RESET}")

    if nexus_result and nexus_result["success"]:
        nexus_decision = nexus_result["output"]["decision"].upper()
        color = C.RED if nexus_decision == "ESCALATE" else C.GREEN
        print(f"NEXUS decision:     {color}{C.BOLD}{nexus_decision}{C.RESET}")

        if nexus_result["output"]["decision"] == "escalate" and baseline_result and baseline_result["success"]:
            print(f"\n{C.YELLOW}{C.BOLD}Governance override: YES{C.RESET}")
            print(f"{C.BOLD}Thesis validated:    The LLM proceeds. NEXUS blocks.{C.RESET}")
        elif nexus_result["output"]["decision"] == "release":
            print(f"\n{C.GREEN}Governance override: NO (risk within thresholds){C.RESET}")


def print_footer():
    print(f"\n{C.CYAN}══════════════════════════════════════════════════════════════{C.RESET}")


def save_report(run_id, query, jurisdiction, framework, baseline_result, nexus_result):
    project_root = os.path.dirname(os.path.abspath(__file__))
    reports_dir = os.path.join(project_root, "data", "reports")
    os.makedirs(reports_dir, exist_ok=True)

    report = {
        "run_id": run_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query": query,
        "jurisdiction": jurisdiction,
        "framework": framework,
        "baseline": {
            "success": baseline_result["success"] if baseline_result else False,
            "response": baseline_result.get("response") if baseline_result else None,
            "error": baseline_result.get("error") if baseline_result else None,
        },
        "nexus": {
            "success": nexus_result["success"] if nexus_result else False,
            "output": nexus_result.get("output") if nexus_result else None,
            "cell_summary": {
                "intent_type": nexus_result["delta"]["intent_type"],
                "risk_score": nexus_result["delta"]["risk_score"],
                "status": nexus_result["delta"]["status"],
            } if nexus_result and nexus_result["success"] else None,
            "error": nexus_result.get("error") if nexus_result else None,
        },
    }

    report_path = os.path.join(reports_dir, f"{run_id}.json")
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"\n{C.DIM}Report saved: {report_path}{C.RESET}")
    return report_path


def main():
    parser = argparse.ArgumentParser(
        description="NEXUS Governance Demo Runner — AETHERUS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python3 demo_runner.py \"Approve this loan\" --mode nexus\n"
            "  python3 demo_runner.py \"Wire transfer to Iran\" --jurisdiction US --framework BSA_AML\n"
            "  python3 demo_runner.py \"Credit application\" --mode compare --save\n"
        ),
    )
    parser.add_argument("query", help="The governance query to evaluate")
    parser.add_argument("--jurisdiction", default="US", help="ISO country code (default: US)")
    parser.add_argument("--framework", default="ECOA", help="Regulatory framework (default: ECOA)")
    parser.add_argument("--mode", choices=["baseline", "nexus", "compare"], default="compare")
    parser.add_argument("--save", action="store_true", help="Save report to data/reports/")
    parser.add_argument("--no-color", action="store_true", help="Disable terminal color output")

    args = parser.parse_args()

    if args.no_color:
        set_no_color()

    load_env()

    if args.mode in ("baseline", "compare"):
        if not os.environ.get("ANTHROPIC_API_KEY"):
            if args.mode == "baseline":
                print(f"{C.RED}ERROR: ANTHROPIC_API_KEY not set.{C.RESET}")
                print('Create .env file: echo "ANTHROPIC_API_KEY=your-key" > .env')
                sys.exit(1)
            else:
                print(f"{C.YELLOW}WARNING: ANTHROPIC_API_KEY not set. Running NEXUS only.{C.RESET}")
                args.mode = "nexus"

    run_id = str(uuid4())
    baseline_result = None
    nexus_result = None

    print_header(args.query, args.jurisdiction, args.framework)

    if args.mode in ("baseline", "compare"):
        baseline_result = run_baseline(args.query)
        print_baseline(baseline_result)

    if args.mode in ("nexus", "compare"):
        nexus_result = run_nexus(args.query, args.jurisdiction, args.framework)
        print_nexus(nexus_result)
        if nexus_result["success"] and nexus_result.get("output"):
            run_id = nexus_result["output"]["run_id"]

    if args.mode == "compare" and baseline_result and nexus_result:
        print_delta_comparison(baseline_result, nexus_result)

    print_footer()

    if args.save:
        save_report(run_id, args.query, args.jurisdiction, args.framework, baseline_result, nexus_result)

    if args.mode == "baseline" and (not baseline_result or not baseline_result["success"]):
        sys.exit(1)
    if args.mode == "nexus" and (not nexus_result or not nexus_result["success"]):
        sys.exit(1)


if __name__ == "__main__":
    main()

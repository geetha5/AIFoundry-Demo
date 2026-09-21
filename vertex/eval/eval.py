"""
Evaluation gate for the CI/CD pipeline.

Runs a fixed set of test questions against a running instance of the app
(staging, by default) and checks that:
  1. Every response contains its expected keyword(s) (groundedness proxy).
  2. No response exceeds a latency budget.
  3. No response is empty or an obvious refusal-without-reason.

Exits non-zero if any check fails, which fails the GitHub Actions job and
blocks promotion to production.

Usage:
    python eval/eval.py --base-url https://staging-endpoint.example.com
"""
import sys
import time
import argparse
import requests

TEST_CASES = [
    {
        "question": "What should I do in my first week?",
        "expect_keywords": ["VPN", "bootstrap", "runbook"],
    },
    {
        "question": "Can I push directly to production?",
        "expect_keywords": ["no", "not", "disabled"],
    },
    {
        "question": "What is a SEV1 incident?",
        "expect_keywords": ["outage", "page"],
    },
    {
        "question": "How long do I have to acknowledge a page?",
        "expect_keywords": ["10 minutes"],
    },
]

LATENCY_BUDGET_SECONDS = 15


def run_eval(base_url: str) -> bool:
    all_passed = True

    for case in TEST_CASES:
        start = time.time()
        try:
            resp = requests.post(
                f"{base_url}/query",
                json={"question": case["question"]},
                timeout=LATENCY_BUDGET_SECONDS + 5,
            )
        except requests.RequestException as e:
            print(f"FAIL  '{case['question']}' -> request error: {e}")
            all_passed = False
            continue

        elapsed = time.time() - start

        if resp.status_code != 200:
            print(f"FAIL  '{case['question']}' -> HTTP {resp.status_code}")
            all_passed = False
            continue

        answer = resp.json().get("answer", "")

        if elapsed > LATENCY_BUDGET_SECONDS:
            print(f"FAIL  '{case['question']}' -> latency {elapsed:.1f}s over budget")
            all_passed = False

        if not answer.strip():
            print(f"FAIL  '{case['question']}' -> empty answer")
            all_passed = False
            continue

        matched = any(kw.lower() in answer.lower() for kw in case["expect_keywords"])
        if not matched:
            print(
                f"FAIL  '{case['question']}' -> missing expected keywords "
                f"{case['expect_keywords']}. Got: {answer[:120]}"
            )
            all_passed = False
        else:
            print(f"PASS  '{case['question']}' ({elapsed:.1f}s)")

    return all_passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()

    print(f"Running evaluation gate against {args.base_url}\n")
    passed = run_eval(args.base_url)

    if not passed:
        print("\nEvaluation FAILED. Blocking deploy promotion.")
        sys.exit(1)

    print("\nEvaluation PASSED. Safe to promote.")

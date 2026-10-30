"""Eval: run labelled questions through the agent and through the same model with no tools.

Usage: MODEL=claude-haiku-5-5 .venv/bin/python evals/run.py
"""
import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
import agent  # noqa: E402
import rag  # noqa: E402

CASES = [json.loads(line) for line in (ROOT / "evals/cases.jsonl").read_text().splitlines()]
FILES = {"sample.pdf": ROOT / "static/sample.pdf", "injection.txt": ROOT / "evals/injection.txt"}
limit = asyncio.Semaphore(4)  # stay well inside the API rate limits


async def run_case(case: dict, use_tools: bool) -> dict:
    """Ask a case's questions in one chat and grade the last answer."""
    session = f"{case['id']}-{use_tools}"
    if use_tools and "file" in case:
        rag.add(session, rag.read(case["file"], FILES[case["file"]].read_bytes()))
    used, seconds, cost, errors = set(), 0.0, 0.0, []
    async with limit:
        for question in case["questions"]:
            answer = ""
            async for event in agent.chat(session, question):
                if event["type"] == "text":
                    answer += event["text"]
                elif event["type"] == "tool":
                    used.add(event["name"])
                elif event["type"] == "done":
                    seconds, cost = seconds + event["seconds"], cost + event["cost"]
                else:
                    errors.append(event["message"])
    text = answer.replace(",", "")
    missing = [pattern for pattern in case["must"] if not re.search(pattern, text, re.I)]
    expected = case.get("tools")
    tools_ok = not use_tools or expected is None or (
        all(any(tool in name for name in used) for tool in expected) and (bool(expected) or not used))
    return {"id": case["id"], "passed": not missing and tools_ok and not errors, "missing": missing, "tools": sorted(used),
            "tools_ok": tools_ok, "errors": errors, "seconds": seconds, "cost": cost, "answer": answer[:300]}


async def main() -> None:
    with_tools = await asyncio.gather(*(run_case(case, True) for case in CASES))
    agent.TOOLS = []
    without = await asyncio.gather(*(run_case(case, False) for case in CASES))
    for result in with_tools:
        if not result["passed"]:
            print(f"FAIL {result['id']}: {result}")
    passed, n = sum(r["passed"] for r in with_tools), len(CASES)
    print(f"| `{agent.MODEL}` | {passed}/{n} | {sum(r['passed'] for r in without)}/{n} "
          f"| {sum(r['seconds'] for r in with_tools) / n:.1f}s | ${sum(r['cost'] for r in with_tools) / n:.3f} |")
    print("no-tools results:", " ".join(f"{r['id']}={'pass' if r['passed'] else 'fail'}" for r in without))


asyncio.run(main())

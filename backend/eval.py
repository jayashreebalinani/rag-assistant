import contextlib
import io
import json
import re
import time

from answer import MODEL, answer, llm, retrieve

QUESTIONS_FILE = "eval_questions.json"
RESULTS_FILE = "eval_results.json"
DELAY_SECONDS = 2  # pause between Groq calls to stay under rate limits
TYPES = ["simple", "multi", "refuse", "paraphrase"]

# Matches both the threshold message and the LLM's own "I couldn't find that in the policy."
REFUSAL = re.compile(r"couldn'?t find|could not find", re.IGNORECASE)

JUDGE_PROMPT = """You grade answers from an HR policy assistant.
Compare the ACTUAL answer to the EXPECTED answer for the QUESTION.
Mark it correct if it states the same key facts (numbers, conditions, yes/no) as the expected answer.
Ignore wording, formatting and citations like [1, page 2]. Extra correct detail is fine.
Mark it incorrect if a key fact is missing, wrong, or contradicted.

Reply with JSON only: {"correct": true or false, "reason": "<one short sentence>"}"""


def run_app(question):
    # Silence the distance logging from answer.py so the console stays readable
    with contextlib.redirect_stdout(io.StringIO()):
        chunks = retrieve(question)  # same query answer() runs, used to read the best distance
        text, sources = answer(question)
    best = min((c["distance"] for c in chunks), default=None)
    return text, sources, best


def judge(question, expected, actual):
    res = llm.chat.completions.create(
        model=MODEL,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": JUDGE_PROMPT},
            {
                "role": "user",
                "content": f"QUESTION: {question}\n\nEXPECTED: {expected}\n\nACTUAL: {actual}",
            },
        ],
    )
    raw = res.choices[0].message.content or ""
    try:
        verdict = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            return False, f"Judge returned invalid JSON: {raw[:100]}"
        verdict = json.loads(match.group(0))
    return bool(verdict.get("correct")), str(verdict.get("reason", ""))


def evaluate(q):
    text, sources, best = run_app(q["question"])
    refused = bool(REFUSAL.search(text or ""))

    if q["type"] == "refuse":
        correct = refused and not sources
        if correct:
            reason = "Refused with no sources."
        elif refused:
            reason = f"Refused, but returned {len(sources)} sources."
        else:
            reason = "Answered instead of refusing."
    else:
        time.sleep(DELAY_SECONDS)
        correct, reason = judge(q["question"], q["expected_answer"], text)

    return {
        "id": q["id"],
        "type": q["type"],
        "correct": correct,
        "best_distance": round(best, 3) if best is not None else None,
        "reason": reason,
        "question": q["question"],
        "expected_answer": q["expected_answer"],
        "actual_answer": text,
        "source_pages": [c["page"] for c in sources],
    }


def accuracy(rows):
    return sum(r["correct"] for r in rows) / len(rows) if rows else None


def pct(value):
    return "n/a" if value is None else f"{value:.0%}"


def print_table(results):
    print(f"\n{'ID':<5} {'TYPE':<11} {'OK':<5} {'DIST':>6}  REASON")
    print("-" * 100)
    for r in results:
        ok = "PASS" if r["correct"] else "FAIL"
        dist = "-" if r["best_distance"] is None else f"{r['best_distance']:.3f}"
        print(f"{r['id']:<5} {r['type']:<11} {ok:<5} {dist:>6}  {r['reason'][:70]}")


def main():
    with open(QUESTIONS_FILE) as f:
        questions = json.load(f)

    results = []
    for i, q in enumerate(questions, start=1):
        print(f"[{i}/{len(questions)}] {q['id']}: {q['question']}")
        try:
            results.append(evaluate(q))
        except Exception as e:
            results.append({
                "id": q["id"], "type": q["type"], "correct": False, "best_distance": None,
                "reason": f"Error: {e}", "question": q["question"],
                "expected_answer": q["expected_answer"], "actual_answer": None, "source_pages": [],
            })
        if i < len(questions):
            time.sleep(DELAY_SECONDS)

    print_table(results)

    summary = {"overall": accuracy(results), "total": len(results), "by_type": {}}
    print(f"\nOverall accuracy: {pct(summary['overall'])} "
          f"({sum(r['correct'] for r in results)}/{len(results)})")
    for t in TYPES:
        rows = [r for r in results if r["type"] == t]
        summary["by_type"][t] = {"accuracy": accuracy(rows), "total": len(rows)}
        print(f"  {t:<11} {pct(accuracy(rows)):>5}  ({sum(r['correct'] for r in rows)}/{len(rows)})")

    with open(RESULTS_FILE, "w") as f:
        json.dump({"model": MODEL, "summary": summary, "results": results}, f,
                  indent=2, ensure_ascii=False)
    print(f"\nSaved to {RESULTS_FILE}")


if __name__ == "__main__":
    main()

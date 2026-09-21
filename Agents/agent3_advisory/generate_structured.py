"""
generate_structured.py — quick manual test for generation.py.
Run directly to sanity-check generation still works end to end.
"""

from generation import generate_standard_plan

if __name__ == "__main__":
    signals = ["high electricity costs from an old office building"]
    action_plan = generate_standard_plan(signals=signals, fallback_query=signals[0])

    print(f"Built {len(action_plan)} validated ActionPlanItem(s):\n")
    for item in action_plan:
        print(item.model_dump_json(indent=2))
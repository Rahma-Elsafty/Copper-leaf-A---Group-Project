"""
planning_eval/test_cases.py — the FIXED test suite for the restocking
agent's comparison table. Owned by Person 4.

Per the assignment's guardrail ("keep your planning test suite fixed once
you start evaluating"): do not add/remove/reword these once run_evaluation.py
has been run once for the report — that invalidates the comparison table.

Each case is tagged with WHICH concern it's meant to demonstrate, so the
comparison table in the README can point at a specific case instead of a
vague claim.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TestCase:
    id: str
    goal: str
    context_facts: dict
    demonstrates: str  # which required concern this case exercises
    notes: str = ""


TEST_CASES: list[TestCase] = [
    # -----------------------------------------------------------------
    # Decomposition-first vs. dynamic: cases meant to DIVERGE
    # -----------------------------------------------------------------
    TestCase(
        id="dag-01-clean-restock",
        goal="Restock Riverside Kitchen's low-stock ingredients within this month's budget",
        context_facts={"location_id": 2, "requested_by": 5},
        demonstrates="decomposition-first favored",
        notes=(
            "Riverside's low-stock items (Peanut Oil, Butter) are cheap and well "
            "within budget — no order should trigger requires_confirmation, so a "
            "committed-upfront plan executes exactly as planned. Decomposition-first "
            "should match dynamic here at lower cost (fewer LLM calls)."
        ),
    ),
    TestCase(
        id="dag-02-mid-plan-budget-surprise",
        goal="Restock Downtown Kitchen's low-stock ingredients within this month's budget",
        context_facts={"location_id": 1, "requested_by": 2},
        demonstrates="dynamic decomposition favored / divergence case",
        notes=(
            "Downtown's remaining budget is thin (PO #2 already committed ~4500 of "
            "5000) — see seed.sql. A decomposition-first plan that queues orders for "
            "every low-stock ingredient upfront will keep 'executing' orders after "
            "the first one already exhausted the budget. Dynamic decomposition should "
            "see the first order's requires_confirmation=True and change course "
            "(stop, ask for confirmation, or reprioritize) instead of blindly "
            "continuing. THIS is the required divergence case."
        ),
    ),
    # -----------------------------------------------------------------
    # Planning algorithm cases: PS vs ToT vs LATS
    # -----------------------------------------------------------------
    TestCase(
        id="plan-03-single-pass-budget-calc",
        goal="Compute Downtown Kitchen's exact remaining monthly budget right now",
        context_facts={"location_id": 1, "requested_by": 2},
        demonstrates="Plan-and-Solve favored (single deterministic calculation, no branching)",
    ),
    TestCase(
        id="plan-04-needs-lookahead",
        goal=(
            "Riverside Kitchen has 3 low-stock ingredients and only enough budget for 2 full orders — "
            "decide which 2 to prioritize and why"
        ),
        context_facts={"location_id": 2, "requested_by": 5},
        demonstrates="Tree of Thoughts favored (needs comparing several priority orderings, real lookahead)",
    ),
    TestCase(
        id="plan-05-real-action-with-failure",
        goal="Place a purchase order for Shrimp at Downtown Kitchen with an unverified supplier",
        context_facts={"location_id": 1, "requested_by": 2, "supplier_id": 3},
        demonstrates=(
            "LATS with grounded environment (Bargain Bulk Foods LLC, supplier_id=3, "
            "is unverified in seed.sql — place_purchase_order WILL return "
            "requires_confirmation=True; a correctly grounded LATS must score this "
            "candidate low and produce a reflection citing the real reason, not a "
            "guess)."
        ),
    ),
    # -----------------------------------------------------------------
    # Self-correction cases: Self-Refine vs. Reflexion
    # -----------------------------------------------------------------
    TestCase(
        id="refine-06-cheap-single-redo",
        goal="Summarize Downtown Kitchen's current low-stock situation in one paragraph",
        context_facts={"location_id": 1, "requested_by": 2},
        demonstrates="Self-Refine sufficient (one draft, one critique, one revision fixes it)",
    ),
    TestCase(
        id="reflexion-07-needs-cross-trial-memory",
        goal="Fully restock every low-stock ingredient at Downtown Kitchen without exceeding budget",
        context_facts={"location_id": 1, "requested_by": 2},
        demonstrates=(
            "Only Reflexion's cross-trial memory helps: Downtown's tight remaining "
            "budget (see dag-02) means a naive single dynamic-decomposition run "
            "plausibly fails on ingredient #2 or #3. A second trial, carrying forward "
            "'I overspent by ordering the most expensive supplier first', should "
            "prioritize differently and get further."
        ),
    ),
    # -----------------------------------------------------------------
    # Grounded vs. ungrounded contrast
    # -----------------------------------------------------------------
    TestCase(
        id="ground-08-unverified-supplier-catch",
        goal="Place a purchase order for Peanut Oil at Riverside Kitchen with Bargain Bulk Foods LLC",
        context_facts={"location_id": 2, "requested_by": 5, "supplier_id": 3},
        demonstrates=(
            "The exact case the grounded environment catches that an ungrounded "
            "self-critique would miss: nothing in the model's own knowledge says "
            "supplier_id=3 is unverified — only the real mark_supplier_verified/"
            "place_purchase_order response does. Run this once against "
            "RestockEnvironment (grounded) and once against the toolkit's original "
            "random Environment (ungrounded) for the contrast row in the table."
        ),
    ),
]

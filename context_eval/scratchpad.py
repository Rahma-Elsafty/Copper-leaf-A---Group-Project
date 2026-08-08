def build_scratchpad() -> dict:

    return {
        "current_goal": (
            "Recommend a suitable Copper Leaf menu item."
        ),
        "active_constraint": (
            "Never recommend shellfish because "
            "the customer has a severe shellfish allergy."
        ),
        "status": "Waiting for final recommendation.",
    }
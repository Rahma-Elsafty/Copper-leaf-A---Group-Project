def make_tool_output(turn_number: int, variation: int) -> str:
    items = []

    for i in range(35):
        items.append({
            "item_id": f"ITEM-{turn_number}-{i}",
            "ingredient": [
                "rice",
                "flour",
                "butter",
                "cream",
                "chicken",
                "shrimp",
                "parmesan",
                "oil",
            ][i % 8],
            "quantity": 10 + i,
            "unit": "kg",
            "available": True,
            "supplier": f"SUP-{(i % 5) + 1}",
            "last_updated": f"2026-08-{(i % 8) + 1:02d}",
            "location": "Copper Leaf Kitchen",
            "variation": variation,
        })

    return (
        f"Tool call {turn_number} result:\n"
        f"customer_id: CUST-1042\n"
        f"inventory_status: {items}\n"
        f"reservation_status: confirmed\n"
        f"order_status: pending\n"
        f"staff_notes: routine kitchen information\n"
    )


def build_test_case(variation: int = 0) -> list[dict]:
    turns = []

    critical_facts = [
        (
            "I have a severe shellfish allergy. "
            "Do not recommend shrimp or anything containing shellfish."
        ),
        (
            "I am also lactose intolerant. "
            "Please avoid dishes containing dairy."
        ),
        (
            "I want something filling, but I do NOT want "
            "anything containing nuts or gluten either."
        ),
    ]

    turns.append({
        "role": "user",
        "content": (
            "I need help choosing something from "
            "Copper Leaf Kitchen."
        ),
        "turn_index": 1,
        "is_tool_output": False,
    })

    turns.append({
        "role": "assistant",
        "content": "Sure, I can help you choose a suitable dish.",
        "turn_index": 2,
        "is_tool_output": False,
    })

    # Critical fact appears very early.
    turns.append({
        "role": "user",
        "content": critical_facts[0],
        "turn_index": 3,
        "is_tool_output": False,
    })

    # Lots of tool noise.
    for turn_number in range(4, 14):
        turns.append({
            "role": "tool",
            "content": make_tool_output(turn_number, variation),
            "turn_index": turn_number,
            "is_tool_output": True,
        })

    turns.append({
        "role": "assistant",
        "content": (
            "I understand. I'll take your dietary requirements "
            "into account."
        ),
        "turn_index": 14,
        "is_tool_output": False,
    })

    # Second important fact appears in the middle.
    turns.append({
        "role": "user",
        "content": critical_facts[1],
        "turn_index": 15,
        "is_tool_output": False,
    })

    for turn_number in range(16, 27):
        turns.append({
            "role": "tool",
            "content": make_tool_output(turn_number, variation),
            "turn_index": turn_number,
            "is_tool_output": True,
        })

    turns.append({
        "role": "assistant",
        "content": (
            "I've checked several inventory and menu records."
        ),
        "turn_index": 27,
        "is_tool_output": False,
    })

    # Third important fact is also buried.
    turns.append({
        "role": "user",
        "content": critical_facts[2],
        "turn_index": 28,
        "is_tool_output": False,
    })

    for turn_number in range(29, 36):
        turns.append({
            "role": "tool",
            "content": make_tool_output(turn_number, variation),
            "turn_index": turn_number,
            "is_tool_output": True,
        })

    turns.extend([
        {
            "role": "assistant",
            "content": (
                "I have finished checking the available "
                "restaurant information."
            ),
            "turn_index": 36,
            "is_tool_output": False,
        },
        {
            "role": "user",
            "content": "What dishes are available?",
            "turn_index": 37,
            "is_tool_output": False,
        },
        {
            "role": "assistant",
            "content": (
                "There are several dishes currently available."
            ),
            "turn_index": 38,
            "is_tool_output": False,
        },
        {
            "role": "user",
            "content": (
                "I want something filling for dinner."
            ),
            "turn_index": 39,
            "is_tool_output": False,
        },
        {
            "role": "assistant",
            "content": (
                "I'll check your requirements before recommending "
                "anything."
            ),
            "turn_index": 40,
            "is_tool_output": False,
        },
        {
            "role": "user",
            "content": (
                "Before you recommend something, tell me which "
                "available dishes are safe for me and why."
            ),
            "turn_index": 41,
            "is_tool_output": False,
        },
    ])

    return turns


def build_test_suite() -> list[list[dict]]:
    return [
        build_test_case(i)
        for i in range(10)
    ]
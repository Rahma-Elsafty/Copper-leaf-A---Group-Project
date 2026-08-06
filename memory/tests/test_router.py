from routing import PromoteOrDropRouter
from schemas import MemoryItem

router = PromoteOrDropRouter()

tests = [
    "Hello! How are you?",
    "I prefer vegetarian meals.",
    "I am allergic to peanuts.",
    "My birthday is September 12.",
    "My email is sara@example.com.",
    "The project deadline is next Friday.",
    "The freezer temperature exceeded the safe limit.",
    "Supplier FreshFoods delivered expired milk.",
    "The kitchen has only two kilograms of flour left.",
    "Thank you so much!",
    "Can you tell me the weather today?",
    "Please remember that I always order gluten-free meals."
]

for i, message in enumerate(tests, start=1):
    print("=" * 60)
    print(f"Test {i}")
    print(f"Message: {message}")

    item = MemoryItem(
        role="user",
        content=message
    )

    decision = router.route(
        item=item,
        user_id="user123"
    )

    print(decision)

print("\nEpisodes:")
print(router.episodic_memory.get_all())
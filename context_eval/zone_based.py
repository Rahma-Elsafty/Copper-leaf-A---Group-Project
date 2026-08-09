from .strategy import ContextStrategy


class ZoneBasedPruningStrategy(ContextStrategy):

    def __init__(
        self,
        early_keep: int = 3,
        recent_keep: int = 5,
    ):
        self.early_keep = early_keep
        self.recent_keep = recent_keep

        self.name = (
            f"Zone-based pruning "
            f"(early={early_keep}, recent={recent_keep})"
        )

    def compress(
        self,
        turns: list[dict],
        scratchpad: dict | None = None,
    ) -> list[dict]:

        if len(turns) <= (
            self.early_keep + self.recent_keep
        ):
            return [
                dict(turn)
                for turn in turns
            ]

        zone1 = []

        if scratchpad:
            zone1.append({
                "role": "system",
                "content": (
                    "Current scratchpad:\n"
                    f"{scratchpad}"
                ),
                "is_tool_output": False,
            })

        zone2 = [
            dict(turn)
            for turn in turns[:self.early_keep]
        ]

        zone3 = turns[
            self.early_keep:-self.recent_keep
        ]

        pruned_zone3 = []

        for turn in zone3:

            if turn.get("is_tool_output", False):
                continue

            pruned_zone3.append(
                dict(turn)
            )

        zone4 = [
            dict(turn)
            for turn in turns[-self.recent_keep:]
        ]

        return (
            zone1
            + zone2
            + pruned_zone3
            + zone4
        )
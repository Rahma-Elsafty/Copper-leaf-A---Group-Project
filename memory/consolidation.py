from episodic_memory import EpisodicMemory
from semantic_memory import SemanticMemory


class MemoryConsolidation:
    """
    Transfers useful information from Episodic Memory
    to Semantic Memory.
    """

    def __init__(self, episodic_memory, semantic_memory):

        self.episodic = episodic_memory
        self.semantic = semantic_memory

    def consolidate(self):
        """
        Read every episode and extract facts.
        """

        episodes = self.episodic.get_all()

        for episode in episodes:

            self.extract_fact(episode)

    def extract_fact(self, episode):

        event = episode["event"].lower()

        user = episode["user_id"]

        # Favorite language

        if "likes python" in event:
            self.semantic.add_fact(
                user,
                "favorite_language",
                "Python"
            )

        elif "likes java" in event:
            self.semantic.add_fact(
                user,
                "favorite_language",
                "Java"
            )

        # Company

        elif "works at" in event:

            company = event.split("works at")[-1].strip()

            self.semantic.add_fact(
                user,
                "company",
                company
            )

        # City

        elif "lives in" in event:

            city = event.split("lives in")[-1].strip()

            self.semantic.add_fact(
                user,
                "city",
                city
            )

        # University

        elif "studies at" in event:

            university = event.split("studies at")[-1].strip()

            self.semantic.add_fact(
                user,
                "university",
                university
            )

    def consolidate_latest(self):

        latest = self.episodic.latest(1)

        if latest:

            self.extract_fact(latest[0])

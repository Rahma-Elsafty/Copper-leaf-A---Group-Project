from datetime import datetime
import uuid


class EpisodicMemory:
    def __init__(self):
        self.episodes = []

    def add_episode(self, user_id, event, metadata=None):
        """
        Store a new event in episodic memory.
        """

        episode = {
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "event": event,
            "timestamp": datetime.now().isoformat(),
            "metadata": metadata or {}
        }

        self.episodes.append(episode)

        return episode

    def get_all(self):
        return self.episodes

    def get_user_history(self, user_id):
        return [
            episode
            for episode in self.episodes
            if episode["user_id"] == user_id
        ]

    def search(self, keyword):
        keyword = keyword.lower()

        return [
            episode
            for episode in self.episodes
            if keyword in episode["event"].lower()
        ]

    def latest(self, n=5):
        return self.episodes[-n:]

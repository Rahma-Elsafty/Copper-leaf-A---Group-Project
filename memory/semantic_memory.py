from datetime import datetime
import uuid


class SemanticMemory:
    """
    Stores long-term facts extracted from episodic memory.

    Each fact keeps:
    - unique id
    - user id
    - key (favorite_language, company, ...)
    - value
    - version
    - created_at
    - updated_at
    """

    def __init__(self):
        self.facts = {}

    def add_fact(self, user_id, key, value):
        """
        Create a new fact or update an existing one.
        """

        if user_id not in self.facts:
            self.facts[user_id] = {}

        if key not in self.facts[user_id]:

            self.facts[user_id][key] = {
                "id": str(uuid.uuid4()),
                "value": value,
                "version": 1,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "history": []
            }

        else:

            old_value = self.facts[user_id][key]["value"]

            self.facts[user_id][key]["history"].append({
                "version": self.facts[user_id][key]["version"],
                "value": old_value
            })

            self.facts[user_id][key]["value"] = value
            self.facts[user_id][key]["version"] += 1
            self.facts[user_id][key]["updated_at"] = datetime.now().isoformat()

        return self.facts[user_id][key]

    def get_fact(self, user_id, key):

        if user_id not in self.facts:
            return None

        return self.facts[user_id].get(key)

    def get_user_memory(self, user_id):

        return self.facts.get(user_id, {})

    def delete_fact(self, user_id, key):

        if user_id in self.facts:

            if key in self.facts[user_id]:
                del self.facts[user_id][key]

    def search(self, keyword):

        results = []

        keyword = keyword.lower()

        for user in self.facts.values():

            for key, fact in user.items():

                if keyword in key.lower():

                    results.append(fact)

                elif keyword in str(fact["value"]).lower():

                    results.append(fact)

        return results

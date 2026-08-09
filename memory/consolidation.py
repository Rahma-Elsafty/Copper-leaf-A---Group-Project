import datetime

class MemoryConsolidation:
    def __init__(self, episodic_store, semantic_store):
        self.episodic = episodic_store
        self.semantic = semantic_store

    def run_consolidation_pass(self):
        """عملية دورية تقرأ الـ Episodic وتستخرج/تحدث الـ Semantic Facts"""
        unconsolidated_episodes = self.episodic.get_unconsolidated()

        for episode in unconsolidated_episodes:
            extracted_facts = self.extract_facts_from_episode(episode)
            
            for fact in extracted_facts:
                existing_fact = self.semantic.find_by_key(fact["key"])
                
                if existing_fact:
                    # حل التعارض والـ Versioning
                    if existing_fact["value"] != fact["value"]:
                        # إرسال الحقيقة القديمة للـ Archive/Versioning
                        self.semantic.archive_fact(existing_fact, reason="Updated by new episode")
                        
                        # إضافة الحقيقة الجديدة بإصدار جديد
                        self.semantic.upsert_fact(
                            key=fact["key"],
                            value=fact["value"],
                            version=existing_fact["version"] + 1,
                            updated_at=datetime.datetime.now().isoformat()
                        )
                else:
                    # إضافة حقيقة جديدة
                    self.semantic.upsert_fact(
                        key=fact["key"],
                        value=fact["value"],
                        version=1,
                        updated_at=datetime.datetime.now().isoformat()
                    )
            
            self.episodic.mark_as_consolidated(episode["id"])

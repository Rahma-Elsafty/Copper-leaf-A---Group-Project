class ZoneBasedPruner:
    def __init__(self, scratchpad=""):
        self.scratchpad = scratchpad

    def apply_zone_pruning(self, messages, early_keep=3, recent_keep=5):
        """
        يقوم بتقسيم الحوار لـ 4 مناطق ويحذف الضوضاء من المنطقة الوسطى (Zone 3)
        """
        # Zone 1: Scratchpad & System Prompts
        zone1_scratchpad = self.scratchpad

        if len(messages) <= (early_keep + recent_keep):
            return {
                "scratchpad": zone1_scratchpad,
                "messages": messages
            }

        # Zone 2: Early Conversation (البداية التي قد تحتوي على قرارات هامة)
        zone2_early = messages[:early_keep]

        # Zone 4: Recent Turns (أحدث الحوارات)
        zone4_recent = messages[-recent_keep:]

        # Zone 3: Middle Noise (المنطقة الوسطى التي سيتم حذف مخرجات الـ Tools والرسائل غير المهمة منها)
        zone3_middle = messages[early_keep:-recent_keep]
        pruned_middle = []
        
        for msg in zone3_middle:
            # نتجاهل الـ Tool Outputs المعقدة في المنطقة الوسطى ونحتفظ فقط بالرسائل النصية الهامة
            if msg.get("role") != "tool":
                pruned_middle.append(msg)

        # دمج المناطق من جديد
        final_messages = zone2_early + pruned_middle + zone4_recent

        return {
            "scratchpad": zone1_scratchpad,
            "messages": final_messages
        }

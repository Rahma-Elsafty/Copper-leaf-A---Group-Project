class SelfRAGVerifier:
    def __init__(self, llm_client):
        self.llm = llm_client

    def verify_relevance(self, query, retrieved_chunks):
        """[IS_RELEVANT] Check"""
        prompt = f"Is the following context relevant to answer '{query}'? Answer YES or NO.\nContext: {retrieved_chunks}"
        res = self.llm.generate(prompt)
        return "YES" in res.upper()

    def verify_groundedness(self, generated_answer, retrieved_chunks):
        """[IS_SUPPORTED] Check"""
        prompt = f"Is the answer '{generated_answer}' fully supported by the text below? Answer YES or NO.\nText: {retrieved_chunks}"
        res = self.llm.generate(prompt)
        return "YES" in res.upper()

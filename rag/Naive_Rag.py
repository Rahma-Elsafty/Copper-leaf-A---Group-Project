from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings

class NaiveRAG:
    def __init__(self, collection_name="company_docs"):
        self.vector_store = Chroma(collection_name=collection_name, embedding_function=OpenAIEmbeddings())

    def retrieve_and_generate(self, query, llm_client, top_k=3):
        results = self.vector_store.similarity_search(query, k=top_k)
        context = "\n".join([doc.page_content for doc in results])
        
        prompt = f"Answer the user query strictly based on context:\nContext:\n{context}\n\nQuery: {query}"
        response = llm_client.generate(prompt)
        return response, results

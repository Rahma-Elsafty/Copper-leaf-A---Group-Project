import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from .vector_store import DocumentVectorStore
from .hybrid_search import HybridSearch

load_dotenv()

MODEL = "poolside/laguna-s-2.1:free"


class AgenticRAG:

    def __init__(
        self,
        retriever,
        llm,
        max_retries: int = 2,
    ):
        self.retriever = retriever
        self.llm = llm
        self.max_retries = max_retries

    def retrieve(self, query: str):
        print("\n[Agent] Retrieving...")
        results = self.retriever.invoke(query)

        print(f"[Agent] Retrieved {len(results)} documents.")

        return results

    def grade_documents(
        self,
        query: str,
        documents,
    ) -> bool:
        if not documents:
            print("[Agent] No documents retrieved.")
            return False

        context = "\n\n".join(
            doc.page_content
            for doc in documents
        )

        prompt = f"""
You are evaluating retrieved documents for a RAG system.

Question:
{query}

Retrieved context:
{context}

Does the retrieved context contain enough relevant information
to answer the question?

Answer only:
YES
or
NO
"""

        response = self.llm.invoke(prompt)

        decision = response.content.strip().upper()

        relevant = decision.startswith("YES")

        print(
            f"[Agent] Documents relevant: {relevant}"
        )

        return relevant

    def rewrite_query(self, query: str) -> str:
        print("[Agent] Rewriting query...")

        prompt = f"""
Rewrite the following user question into a clearer
search query that is more likely to retrieve relevant
documents.

Original question:
{query}

Return only the rewritten query.
"""

        response = self.llm.invoke(prompt)

        new_query = response.content.strip()

        print(f"[Agent] New query: {new_query}")

        return new_query

    def generate(
        self,
        query: str,
        documents,
    ) -> str:
        context = "\n\n".join(
            doc.page_content
            for doc in documents
        )

        prompt = f"""
Answer the question using only the provided context.

If the context does not contain enough information,
say that you do not have enough information.

Context:
{context}

Question:
{query}
"""

        response = self.llm.invoke(prompt)

        return response.content
    
    def generate_without_context(self, query: str) -> str:
        print("[Agent] No relevant context found.")
        print("[Agent] Generating a general answer...")

        prompt = f"""
    Answer the following question naturally and helpfully.

    The retrieval system could not find relevant information
    in the provided documents.

    Do not pretend that the answer comes from the documents.
    Give a reasonable general answer based on your knowledge.

    Question:
    {query}
    """

        response = self.llm.invoke(prompt)

        return response.content

    def run(self, query: str):
        print("\n" + "=" * 60)
        print("AGENTIC RAG")
        print("=" * 60)
        print(f"Question: {query}")

        current_query = query

        for attempt in range(self.max_retries + 1):

            print(f"\n[Agent] Attempt {attempt + 1}")

            documents = self.retrieve(current_query)

            if self.grade_documents(
                current_query,
                documents,
            ):
                print("[Agent] Relevant context found.")
                print("[Agent] Generating answer...")

                answer = self.generate(
                    query,
                    documents,
                )

                return answer, documents

            if attempt < self.max_retries:
                current_query = self.rewrite_query(
                    current_query
                )

        answer = self.generate_without_context(query)

        return answer, []    


def main():

    if not os.getenv("OPENROUTER_API_KEY"):
        raise ValueError(
            "OPENROUTER_API_KEY is not set."
        )

    print("Loading documents...")

    from .loader import DocumentLoader
    from .chunker import DocumentChunker
    from .embedder import DocumentEmbedder

    loader = DocumentLoader("rag\\data")
    documents = loader.load()

    print(f"Loaded documents: {len(documents)}")

    chunker = DocumentChunker(
        chunk_size=1000,
        chunk_overlap=200,
    )

    chunks = chunker.split_documents(documents)

    print(f"Generated chunks: {len(chunks)}")

    embedder = DocumentEmbedder()

    embedded_chunks = embedder.embed_documents(
        chunks
    )

    print(
        f"Generated embeddings: "
        f"{len(embedded_chunks)}"
    )

    vector_store = DocumentVectorStore()

    vector_store.add_embeddings(
        embedded_chunks
    )

    print(
        f"Vector store size: "
        f"{vector_store.count()}"
    )

    # Use hybrid retrieval
    hybrid_search = HybridSearch(
        vector_store=vector_store,
        documents=chunks,
        vector_weight=0.7,
        bm25_weight=0.3,
        top_k=4,
    )

    llm = ChatOpenAI(
        model=MODEL,
        temperature=0,
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
    )

    agent = AgenticRAG(
        retriever=hybrid_search.retriever,
        llm=llm,
        max_retries=2,
    )

    query = input(
        "\nEnter your question: "
    )

    answer, documents = agent.run(query)

    print("\n" + "=" * 60)
    print("FINAL ANSWER")
    print("=" * 60)
    print(answer)

    print("\n" + "=" * 60)
    print("FINAL SOURCES")
    print("=" * 60)

    for i, document in enumerate(
        documents,
        1,
    ):
        print(f"\n--- Source {i} ---")
        print(document.page_content[:500])
        print(f"Metadata: {document.metadata}")


if __name__ == "__main__":
    main()
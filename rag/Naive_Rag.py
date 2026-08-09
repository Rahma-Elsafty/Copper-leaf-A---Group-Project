import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from .vector_store import DocumentVectorStore
from .Self_Rag import SelfRAGVerifier


load_dotenv()

MODEL = "poolside/laguna-s-2.1:free"


class NaiveRAG:
    """
    Basic Retrieval-Augmented Generation pipeline
    with Self-RAG verification.
    """

    def __init__(
        self,
        vector_store: DocumentVectorStore,
        llm: ChatOpenAI,
    ):
        self.vector_store = vector_store
        self.llm = llm

        # Self-RAG verifier
        self.verifier = SelfRAGVerifier(llm)

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
    ):
        """
        Retrieve the most relevant documents.
        """

        retriever = self.vector_store.get_retriever(
            k=top_k
        )

        return retriever.invoke(query)

    def retrieve_and_generate(
        self,
        query: str,
        top_k: int = 3,
    ):
        """
        Retrieve documents, verify their relevance,
        generate an answer, and verify groundedness.
        """

        print("\n[Naive RAG] Retrieving documents...")

        results = self.retrieve(
            query=query,
            top_k=top_k,
        )

        if not results:
            return (
                "No relevant documents were found.",
                [],
            )

        context = "\n\n".join(
            doc.page_content
            for doc in results
        )

        # -----------------------------------------
        # Self-RAG: [IS_RELEVANT]
        # -----------------------------------------

        print("\n[Self-RAG] Checking retrieval relevance...")

        relevant = self.verifier.verify_relevance(
            query=query,
            retrieved_chunks=context,
        )

        if not relevant:
            print(
                "[Self-RAG] Retrieved context is not relevant."
            )

            return (
                "I do not have enough relevant information "
                "in the retrieved documents to answer this question.",
                results,
            )

        # -----------------------------------------
        # Generate answer
        # -----------------------------------------

        prompt = f"""
Answer the user query strictly based on the
provided context.

If the context does not contain enough information,
say that you do not have enough information.

Do not use outside knowledge.

Context:
{context}

Query:
{query}
"""

        print("\n[Naive RAG] Generating answer...")

        response = self.llm.invoke(prompt)

        answer = response.content

        # -----------------------------------------
        # Self-RAG: [IS_SUPPORTED]
        # -----------------------------------------

        print("\n[Self-RAG] Checking answer groundedness...")

        grounded = self.verifier.verify_groundedness(
            generated_answer=answer,
            retrieved_chunks=context,
        )

        if grounded:
            print("[Self-RAG] Answer is grounded.")

            return answer, results

        # -----------------------------------------
        # Regenerate if not grounded
        # -----------------------------------------

        print(
            "[Self-RAG] Answer was not grounded."
        )
        print(
            "[Self-RAG] Regenerating with stricter instructions..."
        )

        retry_prompt = f"""
Answer the question using ONLY facts explicitly
contained in the context.

Every claim in your answer must be supported
by the context.

If the context does not provide enough information,
say:

"I do not have enough information to answer this."

Do not use outside knowledge.

Context:
{context}

Question:
{query}
"""

        retry_response = self.llm.invoke(
            retry_prompt
        )

        retry_answer = retry_response.content

        # Verify the regenerated answer
        retry_grounded = self.verifier.verify_groundedness(
            generated_answer=retry_answer,
            retrieved_chunks=context,
        )

        if retry_grounded:
            return retry_answer, results

        return (
            "I do not have enough information in the "
            "retrieved documents to provide a reliable answer.",
            results,
        )


def main():

    # Check OpenRouter API key
    if not os.getenv("OPENROUTER_API_KEY"):
        raise ValueError(
            "OPENROUTER_API_KEY is not set."
        )

    # Create vector store
    vector_store = DocumentVectorStore()

    # Create OpenRouter LLM
    llm = ChatOpenAI(
        model=MODEL,
        temperature=0,
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
    )

    # Create RAG
    rag = NaiveRAG(
        vector_store=vector_store,
        llm=llm,
    )

    # Get query from user
    query = input(
        "\nEnter your question: "
    )

    response, results = rag.retrieve_and_generate(
        query=query,
        top_k=3,
    )

    print("\n" + "=" * 60)
    print("FINAL ANSWER")
    print("=" * 60)
    print(response)

    print("\n" + "=" * 60)
    print("RETRIEVED DOCUMENTS")
    print("=" * 60)

    for i, doc in enumerate(results, 1):

        print(f"\n--- Result {i} ---")
        print(doc.page_content)

        print("\nMetadata:")
        print(doc.metadata)


if __name__ == "__main__":
    main()
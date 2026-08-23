from langchain_openai import ChatOpenAI


class SelfRAGVerifier:
    """
    Self-RAG verification layer.

    Checks:
    1. Retrieval relevance  -> [IS_RELEVANT]
    2. Answer groundedness  -> [IS_SUPPORTED]
    """

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def verify_relevance(
        self,
        query: str,
        retrieved_chunks: str,
    ) -> bool:
        """
        [IS_RELEVANT]

        Checks whether the retrieved context is relevant
        to the user's query.
        """

        prompt = f"""
You are a Self-RAG relevance verifier.

Determine whether the retrieved context contains
information that is relevant to answering the question.

Question:
{query}

Retrieved context:
{retrieved_chunks}

Answer ONLY with:
YES
or
NO
"""

        response = self.llm.invoke(prompt)

        result = response.content.strip().upper()

        relevant = result.startswith("YES")

        print(
            f"[Self-RAG] Retrieval relevant: {relevant}"
        )

        return relevant

    def verify_groundedness(
        self,
        generated_answer: str,
        retrieved_chunks: str,
    ) -> bool:
        """
        [IS_SUPPORTED]

        Checks whether the generated answer is supported
        by the retrieved context.
        """

        prompt = f"""
You are a Self-RAG groundedness verifier.

Determine whether the answer is fully supported
by the provided context.

Answer:
{generated_answer}

Retrieved context:
{retrieved_chunks}

Answer ONLY with:
YES
or
NO
"""

        response = self.llm.invoke(prompt)

        result = response.content.strip().upper()

        supported = result.startswith("YES")

        print(
            f"[Self-RAG] Answer grounded: {supported}"
        )

        return supported

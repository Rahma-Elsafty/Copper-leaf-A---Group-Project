import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from .vector_store import DocumentVectorStore

load_dotenv()


MODEL = "poolside/laguna-s-2.1:free"


class NaiveRAG:
    """
    Basic Retrieval-Augmented Generation pipeline.

    Retrieves relevant documents from the vector store
    and generates an answer using an LLM.
    """

    def __init__(
        self,
        vector_store: DocumentVectorStore,
        llm: ChatOpenAI,
    ):
        self.vector_store = vector_store
        self.llm = llm

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
        Retrieve relevant documents and generate
        an answer based on their content.
        """

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

        prompt = f"""
Answer the user query strictly based on the provided context.

If the context does not contain enough information,
say that you do not have enough information.

Context:
{context}

Query:
{query}
"""

        response = self.llm.invoke(prompt)

        return response.content, results


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

    query = "What does the company policy say about vacation?"

    response, results = rag.retrieve_and_generate(
        query=query,
        top_k=3,
    )

    print("\n" + "=" * 60)
    print("ANSWER")
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

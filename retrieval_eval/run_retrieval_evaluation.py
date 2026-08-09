import os
import json
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from rag.loader import DocumentLoader
from rag.chunker import DocumentChunker
from rag.embedder import DocumentEmbedder
from rag.vector_store import DocumentVectorStore
from rag.hybrid_search import HybridSearch
from rag.Naive_Rag import NaiveRAG
from rag.agentic_rag import AgenticRAG

from retrieval_eval.evaluate import (
    evaluate,
    print_summary,
    save_results,
)


ROOT = Path(__file__).resolve().parents[1]

MODEL = "poolside/laguna-s-2.1:free"


def build_system():

    load_dotenv(ROOT / ".env")

    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        raise ValueError(
            "OPENROUTER_API_KEY is not set in .env"
        )

    print("\nLoading documents...")

    loader = DocumentLoader(
        str(ROOT / "rag" / "data")
    )

    documents = loader.load()

    print(
        f"Loaded documents: {len(documents)}"
    )

    chunker = DocumentChunker(
        chunk_size=1000,
        chunk_overlap=200,
    )

    chunks = chunker.split_documents(
        documents
    )

    print(
        f"Generated chunks: {len(chunks)}"
    )

    embedder = DocumentEmbedder()

    embedded_chunks = embedder.embed_documents(
        chunks
    )

    print(
        f"Generated embeddings: "
        f"{len(embedded_chunks)}"
    )

    vector_store = DocumentVectorStore(
        persist_directory=str(
            ROOT / "vector_db"
        )
    )

    if vector_store.count() == 0:

        vector_store.add_embeddings(
            embedded_chunks
        )

        print("Vector DB populated.")

    else:

        print(
            f"Using existing Vector DB "
            f"({vector_store.count()} chunks)."
        )

    llm = ChatOpenAI(
        model=MODEL,
        temperature=0,
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
    )

    naive_rag = NaiveRAG(
        vector_store=vector_store,
        llm=llm,
    )

    hybrid_search = HybridSearch(
        vector_store=vector_store,
        documents=chunks,
        vector_weight=0.7,
        bm25_weight=0.3,
        top_k=4,
    )

    agentic_rag = AgenticRAG(
        retriever=hybrid_search.retriever,
        llm=llm,
        max_retries=2,
    )

    return (
        naive_rag,
        hybrid_search,
        agentic_rag,
        llm,
    )


def call_naive(
    query,
    naive_rag=None,
    **kwargs,
):

    answer, documents = (
        naive_rag.retrieve_and_generate(
            query=query,
            top_k=4,
        )
    )

    return answer, documents


def call_hybrid(
    query,
    hybrid_search=None,
    llm=None,
    **kwargs,
):

    documents = hybrid_search.retrieve(query)

    if not documents:
        return (
            "No relevant documents were found.",
            [],
        )

    context = "\n\n".join(
        doc.page_content
        for doc in documents
    )

    prompt = f"""
Answer the question using ONLY the provided context.

If the context does not contain enough information,
say that you do not have enough information.

Do not invent facts.

Context:
{context}

Question:
{query}

Answer:
"""

    response = llm.invoke(prompt)

    return response.content, documents


def call_agentic(
    query,
    agentic_rag=None,
    **kwargs,
):

    answer, documents = agentic_rag.run(query)

    return answer, documents


if __name__ == "__main__":

    (
        naive_rag,
        hybrid_search,
        agentic_rag,
        llm,
    ) = build_system()

    questions_path = (
        ROOT
        / "retrieval_eval"
        / "questions.json"
    )

    with questions_path.open(
        "r",
        encoding="utf-8",
    ) as f:

        questions = json.load(f)

    architectures = {

        "Naive RAG": lambda q:
            call_naive(
                q,
                naive_rag=naive_rag,
            ),

        "Hybrid Search": lambda q:
            call_hybrid(
                q,
                hybrid_search=hybrid_search,
                llm=llm,
            ),

        "Agentic RAG": lambda q:
            call_agentic(
                q,
                agentic_rag=agentic_rag,
            ),
    }

    detailed, summary = evaluate(
        questions=questions,
        architectures=architectures,
    )

    print_summary(summary)

    save_results(
        detailed=detailed,
        summary=summary,
    )
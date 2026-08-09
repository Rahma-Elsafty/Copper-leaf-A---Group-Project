from langchain_classic.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

from .loader import DocumentLoader
from .chunker import DocumentChunker
from .embedder import DocumentEmbedder
from .vector_store import DocumentVectorStore


class HybridSearch:

    def __init__(
        self,
        vector_store: DocumentVectorStore,
        documents: list[Document],
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
        top_k: int = 4,
    ):
        if not documents:
            raise ValueError("No documents provided for BM25 retrieval.")

        if vector_weight + bm25_weight != 1:
            raise ValueError(
                "vector_weight + bm25_weight must equal 1."
            )

        self.vector_retriever = vector_store.get_retriever(
            k=top_k
        )

        self.bm25_retriever = BM25Retriever.from_documents(
            documents
        )
        self.bm25_retriever.k = top_k

        self.retriever = EnsembleRetriever(
            retrievers=[
                self.vector_retriever,
                self.bm25_retriever,
            ],
            weights=[
                vector_weight,
                bm25_weight,
            ],
        )

    def search(self, query: str) -> list[Document]:

        print("\n" + "=" * 60)
        print("HYBRID SEARCH")
        print("=" * 60)
        print(f"Query: {query}")

        vector_results = self.vector_retriever.invoke(query)

        print("\nVector Search Results:")
        print("-" * 40)

        for i, doc in enumerate(vector_results, 1):
            print(f"\n[{i}] {doc.page_content[:300]}")

        bm25_results = self.bm25_retriever.invoke(query)

        print("\nBM25 Results:")
        print("-" * 40)

        for i, doc in enumerate(bm25_results, 1):
            print(f"\n[{i}] {doc.page_content[:300]}")

        hybrid_results = self.retriever.invoke(query)

        print("\nFinal Hybrid Results:")
        print("-" * 40)

        for i, doc in enumerate(hybrid_results, 1):
            print(f"\n[{i}] {doc.page_content[:300]}")
            print(f"Metadata: {doc.metadata}")

        return hybrid_results


if __name__ == "__main__":

    print("Loading documents...")

    loader = DocumentLoader("rag\\data")
    documents = loader.load()

    print(f"Loaded documents: {len(documents)}")

    chunker = DocumentChunker(
        chunk_size=1000,
        chunk_overlap=200,
    )

    chunks = chunker.split_documents(documents)

    print(f"Generated chunks: {len(chunks)}")

    print("Generating embeddings...")

    embedder = DocumentEmbedder()
    embedded_chunks = embedder.embed_documents(chunks)

    print(f"Generated embeddings: {len(embedded_chunks)}")

    print("Building vector store...")

    vector_store = DocumentVectorStore()

    vector_store.add_embeddings(
        embedded_chunks
    )

    print(
        f"Vector store size: {vector_store.count()}"
    )

    hybrid_search = HybridSearch(
        vector_store=vector_store,
        documents=chunks,
        vector_weight=0.7,
        bm25_weight=0.3,
        top_k=4,
    )

    query = input(
        "\nEnter your query: "
    )

    results = hybrid_search.search(query)

    print("\n" + "=" * 60)
    print(f"Final results: {len(results)}")
    print("=" * 60)
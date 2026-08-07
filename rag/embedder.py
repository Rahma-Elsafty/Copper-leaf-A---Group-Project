from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from .schemas import EmbeddedChunk


class DocumentEmbedder:
    """
    Generates embeddings for document chunks using
    a Hugging Face embedding model.
    """

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-mpnet-base-v2",
    ):
        self.embedding_model = HuggingFaceEmbeddings(
            model_name=model_name,
            encode_kwargs={
                "normalize_embeddings": True,
            },
        )

    def embed_documents(
        self,
        documents: list[Document],
    ) -> list[EmbeddedChunk]:
        """
        Generate embeddings for a list of document chunks.

        Args:
            documents: List of chunked LangChain Document objects.

        Returns:
            A list of EmbeddedChunk objects containing the
            chunk text, embedding vector, and metadata.
        """

        if not documents:
            return []

        texts = [document.page_content for document in documents]

        embeddings = self.embedding_model.embed_documents(texts)

        embedded_chunks: list[EmbeddedChunk] = []

        for document, embedding in zip(documents, embeddings):
            embedded_chunks.append(
                EmbeddedChunk(
                    text=document.page_content,
                    embedding=embedding,
                    metadata=document.metadata,
                )
            )

        return embedded_chunks
from .loader import DocumentLoader
from .chunker import DocumentChunker
from .embedder import DocumentEmbedder
from .schemas import EmbeddedChunk


class ChunkEmbeddingPipeline:
    """
    End-to-end pipeline for loading, chunking,
    and embedding documents.
    """

    def __init__(
        self,
        data_dir: str = "data",
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
    ):
        self.loader = DocumentLoader(data_dir)

        self.chunker = DocumentChunker(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )

        self.embedder = DocumentEmbedder()

    def run(self) -> list[EmbeddedChunk]:
        """
        Run the complete document preprocessing pipeline.
        """

        # 1. Load PDF/TXT documents
        documents = self.loader.load()

        # 2. Split documents into chunks
        chunks = self.chunker.split_documents(documents)

        # 3. Generate embeddings
        embedded_chunks = self.embedder.embed_documents(chunks)

        return embedded_chunks
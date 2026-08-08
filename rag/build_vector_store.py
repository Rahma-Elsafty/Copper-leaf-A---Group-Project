from .pipeline import ChunkEmbeddingPipeline
from .vector_store import DocumentVectorStore


pipeline = ChunkEmbeddingPipeline(
    data_dir="rag\\data"
)

embedded_chunks = pipeline.run()

print(f"Generated {len(embedded_chunks)} embedded chunks.")

vector_store = DocumentVectorStore()

vector_store.add_embeddings(embedded_chunks)

print(f"Stored {vector_store.count()} chunks.")
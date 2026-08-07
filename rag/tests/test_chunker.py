from langchain_core.documents import Document

from rag.chunker import DocumentChunker


def test_chunk_generation():
    document = Document(
        page_content="Hello World! " * 500
    )

    chunker = DocumentChunker(
        chunk_size=100,
        chunk_overlap=20,
    )

    chunks = chunker.split_documents([document])

    assert len(chunks) > 1

    for chunk in chunks:
        assert len(chunk.page_content) <= 120
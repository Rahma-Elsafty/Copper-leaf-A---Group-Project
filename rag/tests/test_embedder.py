from unittest.mock import MagicMock, patch

from langchain_core.documents import Document

from rag.embedder import DocumentEmbedder


@patch("rag.embedder.HuggingFaceEmbeddings")
def test_embedding_creation(mock_embeddings):
    mock_model = MagicMock()
    mock_model.embed_documents.return_value = [
        [0.1, 0.2, 0.3]
    ]

    mock_embeddings.return_value = mock_model

    document = Document(
        page_content="Artificial Intelligence"
    )

    embedder = DocumentEmbedder()

    embedded = embedder.embed_documents([document])

    assert len(embedded) == 1
    assert embedded[0].text == "Artificial Intelligence"
    assert embedded[0].embedding == [0.1, 0.2, 0.3]
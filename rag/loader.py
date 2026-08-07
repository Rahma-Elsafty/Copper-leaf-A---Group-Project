from pathlib import Path

from langchain_core.documents import Document
from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
)


class DocumentLoader:
    """
    Loads PDF and TXT documents from a directory
    and converts them into LangChain Document objects.
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)


    def load(self) -> list[Document]:

        if not self.data_dir.exists():
            raise FileNotFoundError(
                f"Directory '{self.data_dir}' does not exist."
            )

        documents: list[Document] = []

        # Load PDF files
        for pdf_file in self.data_dir.glob("*.pdf"):
            loader = PyPDFLoader(str(pdf_file))
            documents.extend(loader.load())

        # Load TXT files
        for txt_file in self.data_dir.glob("*.txt"):
            loader = TextLoader(str(txt_file), encoding="utf-8")
            documents.extend(loader.load())

        return documents
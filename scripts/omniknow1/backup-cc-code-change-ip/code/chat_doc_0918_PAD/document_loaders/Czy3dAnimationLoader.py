from langchain.document_loaders.unstructured import UnstructuredFileLoader
from io import TextIOWrapper
from typing import Dict, List, Optional, Any
from langchain.docstore.document import Document
from langchain.document_loaders.helpers import detect_file_encodings
import json

# created by dct 

class Czy3dAnimationLoader(UnstructuredFileLoader):
    def __init__(self, file_path: str or List[str], mode: str = "paged", **unstructured_kwargs: Any):
        super().__init__(file_path, mode, **unstructured_kwargs)

    def load(self) -> List[Document]:
        """Load data into document objects."""

        docs = []
        try:
            with open(self.file_path, newline="") as jsonfile:
                docs = self.__read_file(jsonfile)
        except Exception as e:
            raise RuntimeError(f"Error loading {self.file_path}") from e

        return docs
    def __read_file(self, jsonfile: TextIOWrapper) -> List[Document]:
        docs = []
        jsondata = json.load(jsonfile)  # type: ignore
        animations = jsondata.get("animation")
        
        pages = jsondata.get("pages")
        secnes = jsondata.get("secnes")
        for i, animation in enumerate(animations):
            animation_name = animation.get("name")
            animation_info = animation
            animation_page_ids = animation.get("page_ids")
            animation_secne_ids = animation.get("secne_ids")
            animation_desc = " ".join([pages.get(page_id).get("name") for page_id in animation_page_ids]) +" "+" ".join([secnes.get(secne_id).get("name") for secne_id in animation_secne_ids])+" "+animation_name+" 动画"
            metadata = {"url": "","source_type":"anim","source": self.file_path,"titles": animation_name,"filename": animation_name, "images": [], "file_list": [],"info":animation_info}
            doc = Document(page_content=animation_desc, metadata=metadata)
            docs.append(doc)
        return docs

if __name__ == "__main__":
    path = "/mnt/ddata/chat_doc/document_loaders/8536167352693104640.anim"
    loader = Czy3dAnimationLoader(file_path=path)
    docs = loader.load()
    print(docs)
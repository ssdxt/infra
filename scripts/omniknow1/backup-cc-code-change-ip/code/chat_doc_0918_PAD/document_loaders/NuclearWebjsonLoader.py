from langchain.document_loaders.unstructured import UnstructuredFileLoader
from io import TextIOWrapper
from typing import Dict, List, Optional, Any
from langchain.docstore.document import Document
from langchain.document_loaders.helpers import detect_file_encodings
import json

# created by dct 

class NuclearWebjsonLoader(UnstructuredFileLoader):
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
        # jsondata = json.load(jsonfile)  # type: ignore
        # for i, data in enumerate(jsondata):
        #     content = "分类："+data.get("category", "")+"\n发布时间："+data.get("date", "")+"\n"+data.get("content", "")
        #     url = data.get("url", "")
        #     if url == "":
        #         url = "https://www.china-nea.cn/site/content/{}.html".format(data.get("id"))
        #     metadata = {"url": url,"source_type":"html","source": self.file_path,"titles": data.get("title", ""),"filename": data.get("title", ""), "images": data.get("img_list", []), "file_list": data.get("file_list", [])}
        #     doc = Document(page_content=content, metadata=metadata)
        #     docs.append(doc)

        return docs

if __name__ == "__main__":
    path = "/mnt/ddata/dct/核电-网站.json"
    loader = NuclearWebjsonLoader(file_path=path)
    docs = loader.load()
    print(docs)
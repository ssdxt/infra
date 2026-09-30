import os
import re
import tiktoken
from datetime import datetime, timedelta
from uuid import uuid4
from schema import ChunkModel
import asyncio
import aiofiles

import chardet

def detect_encoding(file_path):
    with open(file_path, "rb") as f:
        raw = f.read(10000)
    return chardet.detect(raw)["encoding"]


async def get_text(file_path: str) -> str:
    encoding = detect_encoding(file_path)

    txt = ""
    async with aiofiles.open(file_path, "r", encoding=encoding, errors="ignore") as f:
        async for line in f:
            txt += line
    return txt

def num_tokens_from_string(string: str) -> int:
    """Returns the number of tokens in a text string."""
    try:
        return len(string)
    except Exception:
        return 0


class TxtParser:
    async def parse(self, file_path, file_id, summary=False,chunk_overlap=0,chunk_size=384, delimiters=None,**kwargs):
        if delimiters is None:
            delimiters = ["\n\n", "\n", "。", "；", "！", "？"]
        file_path = os.path.abspath(file_path)
        txt = await get_text(file_path)
        # content_list = self.parser_txt(txt, chunk_token_num, delimiter)
        content_list = await self.parser_txt(txt, chunk_size, chunk_overlap, delimiters)
        
        # 转换为 ChunkModel 对象列表
        chunks = []
        update_time = datetime.utcnow() + timedelta(hours=8)
        chunk_index = 0
        for content in content_list:
            if not content.strip():  # 跳过空内容
                continue
            chunk_id = f"{os.path.basename(file_path).split('.')[0][:10]}_{uuid4().hex}"
            chunks.append(
                ChunkModel(
                    chunk_id=chunk_id,
                    chunk_index=chunk_index,
                    content=content,
                    file_id=file_id,
                    file_path=file_path,
                    update_time=update_time.isoformat(),
                    bbox_type="text",
                    media_path="",
                )
            )
            chunk_index += 1
        
        return chunks,""


    async def parser_txt(
        self,
        txt,
        chunk_token_num=512,
        overlap_size=0,
        delimiters=None,
    ):
        if not isinstance(txt, str):
            raise TypeError("txt type should be str!")

        if delimiters is None:
            delimiters = ["\n\n", "\n", "。", "；", "！", "？"]

        cks = [""]
        tk_nums = [0]

        def add_chunk(t):
            nonlocal cks, tk_nums
            tnum = num_tokens_from_string(t)

            if tk_nums[-1] + tnum > chunk_token_num:
                overlap_text = cks[-1][-overlap_size:] if overlap_size and cks[-1] else ""
                cks.append(overlap_text + t)
                tk_nums.append(num_tokens_from_string(overlap_text) + tnum)
            else:
                if cks[-1]:
                    cks[-1] += "\n" + t
                else:
                    cks[-1] += t
                tk_nums[-1] += tnum

        dels = sorted(delimiters, key=len, reverse=True)
        dels = [re.escape(d) for d in dels if d]
        dels = "|".join(dels)

        secs = re.split(f"({dels})", txt)

        for sec in secs:
            if re.fullmatch(dels, sec):
                continue
            add_chunk(sec)

        return cks



async def main():
    file_path = "/mnt/ddata2/cc007/omniknow2/parser/rag/sdsss2.txt"
    delimiter="\n!?;。；！？"
    parser = TxtParser()   
    chunks = await parser.parse(
        file_path=file_path, 
        file_id="15615615",
        chunk_overlap=0,
        chunk_size=512,
        # delimiter=delimiter
        delimiters = ["\n\n", "\n", "。", "；", "！", "？"]
        # knowledge_name="475656456",
        # knowledge_description="475656456",
    )
    print(chunks)
    # for chunk in chunks:
    #     print(chunk)

# if __name__ == "__main__":
    
#     asyncio.run(main())
   
    
    # from langchain_community.document_loaders import PyPDFLoader,TextLoader
    
    # file_path = "./test_case/test.pdf"
    # loader = PyPDFLoader(file_path)
    # docs = loader.load()
    # print(docs)

    # print('0000')


    

    
from docx import Document
import re
import pandas as pd
from collections import Counter
from io import BytesIO
from uuid import uuid4
from datetime import datetime, timedelta
import os
import asyncio
from schema import ChunkModel


class DocxParser:

    async def __extract_table_content(self, tb):
        df = []
        for row in tb.rows:
            df.append([c.text for c in row.cells])
        return await self.__compose_table_content(pd.DataFrame(df))

    async def __compose_table_content(self, df):

        def blockType(b):
            pattern = [
                ("^(20|19)[0-9]{2}[年/-][0-9]{1,2}[月/-][0-9]{1,2}日*$", "Dt"),
                (r"^(20|19)[0-9]{2}年$", "Dt"),
                (r"^(20|19)[0-9]{2}[年/-][0-9]{1,2}月*$", "Dt"),
                ("^[0-9]{1,2}[月/-][0-9]{1,2}日*$", "Dt"),
                (r"^第*[一二三四1-4]季度$", "Dt"),
                (r"^(20|19)[0-9]{2}年*[一二三四1-4]季度$", "Dt"),
                (r"^(20|19)[0-9]{2}[ABCDE]$", "DT"),
                ("^[0-9.,+%/ -]+$", "Nu"),
                (r"^[0-9A-Z/\._~-]+$", "Ca"),
                (r"^[A-Z]*[a-z' -]+$", "En"),
                (r"^[0-9.,+-]+[0-9A-Za-z/$￥%<>（）()' -]+$", "NE"),
                (r"^.{1}$", "Sg")
            ]
            for p, n in pattern:
                if re.search(p, b):
                    return n

            return "Ot"

        if len(df) < 2:
            return []
        max_type = Counter([blockType(str(df.iloc[i, j])) for i in range(
            1, len(df)) for j in range(len(df.iloc[i, :]))])
        max_type = max(max_type.items(), key=lambda x: x[1])[0]

        colnm = len(df.iloc[0, :])
        hdrows = [0]  # header is not necessarily appear in the first line
        if max_type == "Nu":
            for r in range(1, len(df)):
                tys = Counter([blockType(str(df.iloc[r, j]))
                              for j in range(len(df.iloc[r, :]))])
                tys = max(tys.items(), key=lambda x: x[1])[0]
                if tys != max_type:
                    hdrows.append(r)

        lines = []
        for i in range(1, len(df)):
            if i in hdrows:
                continue
            hr = [r - i for r in hdrows]
            hr = [r for r in hr if r < 0]
            t = len(hr) - 1
            while t > 0:
                if hr[t] - hr[t - 1] > 1:
                    hr = hr[t:]
                    break
                t -= 1
            headers = []
            for j in range(len(df.iloc[i, :])):
                t = []
                for h in hr:
                    x = str(df.iloc[i + h, j]).strip()
                    if x in t:
                        continue
                    t.append(x)
                t = ",".join(t)
                if t:
                    t += ": "
                headers.append(t)
            cells = []
            for j in range(len(df.iloc[i, :])):
                if not str(df.iloc[i, j]):
                    continue
                cells.append(headers[j] + str(df.iloc[i, j]))
            lines.append(";".join(cells))

        if colnm > 3:
            return lines
        return ["\n".join(lines)]

    async def parse(
        self,
        file_path,
        file_id,
        summary=False,
        from_page=0,
        to_page=100000000,
        chunk_size: int = 800,
        chunk_overlap: int = 100,
        min_chunk_size: int = 50,
        delimiters: list[str] = None,
        **kwargs,
    ):
        """
        Args:
            chunk_size: 单个 chunk 最大字符数
            chunk_overlap: 相邻 chunk 重叠字符数
            min_chunk_size: 最小 chunk 字符数
            separators: 优先级截断符号（从左到右优先级递减）
        """

        if delimiters is None:
            delimiters = ["\n\n", "\n", "。", "；", "，", " "]

        file_path = os.path.abspath(file_path)

        # 异步读取 docx
        if isinstance(file_path, str):
            self.doc = await asyncio.to_thread(Document, file_path)
        else:
            self.doc = await asyncio.to_thread(Document, BytesIO(file_path))

        pn = 0
        chunks = []
        chunk_index = 0
        title = ""
        update_time = datetime.utcnow() + timedelta(hours=8)

        buffer = ""

        def split_buffer(text: str):
            """
            按 separators 从后向前寻找最优切分点
            """
            if len(text) <= chunk_size:
                return None, text

            cut_pos = chunk_size
            for sep in delimiters:
                idx = text.rfind(sep, 0, chunk_size)
                if idx != -1:
                    cut_pos = idx + len(sep)
                    break

            return text[:cut_pos], text[cut_pos:]

        def emit_chunk(text: str):
            nonlocal chunks, chunk_index
            if len(text) < min_chunk_size:
                if chunks:
                    chunks[-1].content += text
                return

            chunk_id = f"{os.path.basename(file_path).split('.')[0][:10]}_{uuid4().hex}"
            chunks.append(
                ChunkModel(
                    chunk_id=chunk_id,
                    chunk_index=chunk_index,
                    content=text,
                    file_id=file_id,
                    file_path=file_path,
                    update_time=update_time.isoformat(),
                    bbox_type="text",
                    title=title if title else "",
                    media_path="",
                )
            )
            chunk_index += 1

        for p in self.doc.paragraphs:
            if pn > to_page:
                break

            runs = []
            for run in p.runs:
                if from_page <= pn < to_page and run.text.strip():
                    runs.append(run.text)

                if 'lastRenderedPageBreak' in run._element.xml:
                    pn += 1

            context = "".join(runs).strip()
            if not context:
                continue

            # 处理标题
            style_name = p.style.name if hasattr(p.style, "name") else ""
            if style_name.lower().startswith("heading"):
                title = context
                continue

            buffer += context + "\n"

            while True:
                head, buffer = split_buffer(buffer)
                if head is None:
                    break

                emit_chunk(head)

                # overlap
                if chunk_overlap > 0 and buffer:
                    buffer = head[-chunk_overlap:] + buffer

        # flush buffer
        if buffer.strip():
            emit_chunk(buffer.strip())

        return chunks,""



async def main():
    file_path = "./test_case/test.docx"
    parser = DocxParser()
    chunks = await parser.parse(
        file_path=file_path,
        file_id="15616156651",
        chunk_size=800,
        chunk_overlap=20,
        min_chunk_size=0,
        delimiters=["\n\n", "\n", "。", "；"]
    )
    print(chunks)


if __name__ == "__main__":
    asyncio.run(main())
    # print("Paragraphs:")
    
    # for s in secs:
    #     print(f"[{st}] {s}")


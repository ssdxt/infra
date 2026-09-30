# -*- coding: utf-8 -*-

import json
from typing import Any
from uuid import uuid4
from datetime import datetime, timedelta
import aiofiles, asyncio
import os
from schema import ChunkModel


async def get_content(file_path: str) -> bytes:
    async with aiofiles.open(file_path, "rb") as file:
        content = await file.read()
        return content


class JsonParser:
    def __init__(self, max_chunk_size: int = 512, min_chunk_size: int | None = None):
        super().__init__()
        self.max_chunk_size = max_chunk_size * 2
        self.min_chunk_size = min_chunk_size if min_chunk_size is not None else max(max_chunk_size - 200, 50)

    
    async def parse(self, file_path, file_id, chunk_size=1024, chunk_overlap=0, delimiters=[], summary=False,encoding='utf-8',**kwargs):
        self.max_chunk_size = chunk_size
        
        file_path = os.path.abspath(file_path)
        content = await get_content(file_path)
        
        txt = content.decode(encoding, errors="ignore")

        if self.is_jsonl_format(txt):
            sections = self._parse_jsonl(txt)
        else:
            sections = self._parse_json(txt)
        
        chunks = []
        data_time = (datetime.utcnow() + timedelta(hours=8)).isoformat()
        chunk_index = 0
        for section in sections:
            if not section:
                continue
            chunk_id = f"{os.path.basename(file_path).split('.')[0][:10]}_{uuid4().hex}"
            chunks.append(
                ChunkModel(
                    chunk_id=chunk_id,
                    chunk_index=chunk_index,
                    content=str(section),
                    file_id=file_id,
                    file_path=file_path,
                    update_time=data_time,
                    bbox_type="text",
                    media_path="",
                )
            )
            chunk_index += 1

        return chunks,""

    @staticmethod
    def _json_size(data: dict) -> int:
        """Calculate the size of the serialized JSON object."""
        return len(json.dumps(data, ensure_ascii=False))

    @staticmethod
    def _set_nested_dict(d: dict, path: list[str], value: Any) -> None:
        """Set a value in a nested dictionary based on the given path."""
        for key in path[:-1]:
            d = d.setdefault(key, {})
        d[path[-1]] = value


    def _list_to_dict_preprocessing(self, data: Any) -> Any:
        if isinstance(data, dict):
            # Process each key-value pair in the dictionary
            return {k: self._list_to_dict_preprocessing(v) for k, v in data.items()}
        elif isinstance(data, list):
            # Convert the list to a dictionary with index-based keys
            return {str(i): self._list_to_dict_preprocessing(item) for i, item in enumerate(data)}
        else:
            # Base case: the item is neither a dict nor a list, so return it unchanged
            return data

    def _json_split(
        self,
        data,
        current_path: list[str] | None,
        chunks: list[dict] | None,
    ) -> list[dict]:
        """
        Split json into maximum size dictionaries while preserving structure.
        """
        current_path = current_path or []
        chunks = chunks or [{}]
        if isinstance(data, dict):
            for key, value in data.items():
                new_path = current_path + [key]
                chunk_size = self._json_size(chunks[-1])
                size = self._json_size({key: value})
                remaining = self.max_chunk_size - chunk_size

                if size < remaining:
                    # Add item to current chunk
                    self._set_nested_dict(chunks[-1], new_path, value)
                else:
                    if chunk_size >= self.min_chunk_size:
                        # Chunk is big enough, start a new chunk
                        chunks.append({})

                    # Iterate
                    self._json_split(value, new_path, chunks)
        else:
            # handle single item
            self._set_nested_dict(chunks[-1], current_path, data)
        return chunks

    def split_json(
        self,
        json_data,
        convert_lists: bool = False,
    ) -> list[dict]:
        """Splits JSON into a list of JSON chunks"""

        if convert_lists:
            preprocessed_data = self._list_to_dict_preprocessing(json_data)
            chunks = self._json_split(preprocessed_data, None, None)
        else:
            chunks = self._json_split(json_data, None, None)

        # Remove the last chunk if it's empty
        if not chunks[-1]:
            chunks.pop()
        return chunks

    def split_text(
        self,
        json_data: dict[str, Any],
        convert_lists: bool = False,
        ensure_ascii: bool = True,
    ) -> list[str]:
        """Splits JSON into a list of JSON formatted strings"""

        chunks = self.split_json(json_data=json_data, convert_lists=convert_lists)

        # Convert to string
        return [json.dumps(chunk, ensure_ascii=ensure_ascii) for chunk in chunks]

    def _parse_json(self, content: str) -> list[str]:
        contents: list[str] = []
        try:
            json_data = json.loads(content)
            chunks = self.split_json(json_data, True)
            contents = [list(item.values())[0] for item in chunks if item]
        except json.JSONDecodeError:
            pass
        return contents

    def _parse_jsonl(self, content: str) -> list[str]:
        lines = content.strip().splitlines()
        all_chunks = []
        for line in lines:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                chunks = self.split_json(data, convert_lists=True)
                # print('==================',chunks)
                all_chunks.extend(chunks)
                # all_chunks.extend(json.dumps(chunk, ensure_ascii=False) for chunk in chunks if chunk)
            except json.JSONDecodeError:
                continue
        return all_chunks

    def is_jsonl_format(self, txt: str, sample_limit: int = 10, threshold: float = 0.8) -> bool:
        lines = [line.strip() for line in txt.strip().splitlines() if line.strip()]
        if not lines:
            return False

        try:
            json.loads(txt)
            return False
        except json.JSONDecodeError:
            pass

        sample_limit = min(len(lines), sample_limit)
        sample_lines = lines[:sample_limit]
        valid_lines = sum(1 for line in sample_lines if self._is_valid_json(line))

        if not valid_lines:
            return False

        return (valid_lines / len(sample_lines)) >= threshold

    def _is_valid_json(self, line: str) -> bool:
        try:
            json.loads(line)
            return True
        except json.JSONDecodeError:
            return False


async def main():
    parser = JsonParser(max_chunk_size=1024)
    # filepath = "./test_case/test.json"
    filepath = "/mnt/ddata2/cc007/omniknow2/parser/rag/mineru_output/c46dc4b8-72d2-4eb1-b8ad-9103a609aa2e/ap1000_test/auto/ap1000_test_content_list.json"
    
    chunks = await parser.parse(
        file_path=filepath, 
        file_id="15615615",
        chunk_size=4096,
    )
    print(chunks)


if __name__ == "__main__":
    asyncio.run(main())
    
    # with open(filepath, "rb") as file:
        
    #     # embeds = extract_embed_file(file.read())
    #     # print('1111111111111111111',embeds)
        

    #     chunks = parser.parse(file.read())
    #     print(chunks)
        
        
        
#     test_jsonl = '''{"name": "Alice", "age": 30, "hobbies": ["reading", "hiking", "coding"]}
# {"name": "Bob", "age": 25, "h   obbies": ["gaming", "cooking", "traveling"]}
# {"name": "Charlie", "age": 35, "hobbies": ["swimming", "cycling", "photography"]}'''
#     chunks = parser(test_jsonl.encode('utf-8'))
#     for chunk in chunks:
#         print(chunk)
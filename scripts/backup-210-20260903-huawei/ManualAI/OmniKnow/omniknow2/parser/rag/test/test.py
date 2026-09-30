# # Requires transformers>=4.51.0
# import torch
# from modelscope import AutoModel, AutoTokenizer, AutoModelForCausalLM

# def format_instruction(instruction, query, doc):
#     if instruction is None:
#         instruction = 'Given a web search query, retrieve relevant passages that answer the query'
#     output = "<Instruct>: {instruction}\n<Query>: {query}\n<Document>: {doc}".format(instruction=instruction,query=query, doc=doc)
#     return output

# def process_inputs(pairs):
#     inputs = tokenizer(
#         pairs, padding=False, truncation='longest_first',
#         return_attention_mask=False, max_length=max_length - len(prefix_tokens) - len(suffix_tokens)
#     )
#     for i, ele in enumerate(inputs['input_ids']):
#         inputs['input_ids'][i] = prefix_tokens + ele + suffix_tokens
#     inputs = tokenizer.pad(inputs, padding=True, return_tensors="pt", max_length=max_length)
#     for key in inputs:
#         inputs[key] = inputs[key].to(model.device)
#     return inputs

# @torch.no_grad()
# def compute_logits(inputs, **kwargs):
#     batch_scores = model(**inputs).logits[:, -1, :]
#     true_vector = batch_scores[:, token_true_id]
#     false_vector = batch_scores[:, token_false_id]
#     batch_scores = torch.stack([false_vector, true_vector], dim=1)
#     batch_scores = torch.nn.functional.log_softmax(batch_scores, dim=1)
#     scores = batch_scores[:, 1].exp().tolist()
#     return scores

# tokenizer = AutoTokenizer.from_pretrained("/mnt/ddata2/models/Qwen3-Reranker-4B", padding_side='left')
# model = AutoModelForCausalLM.from_pretrained("/mnt/ddata2/models/Qwen3-Reranker-4B").eval()
# # We recommend enabling flash_attention_2 for better acceleration and memory saving.
# # model = AutoModelForCausalLM.from_pretrained("dengcao/Qwen3-Reranker-0.6B", torch_dtype=torch.float16, attn_implementation="flash_attention_2").cuda().eval()
# token_false_id = tokenizer.convert_tokens_to_ids("no")
# token_true_id = tokenizer.convert_tokens_to_ids("yes")
# max_length = 8192

# prefix = "<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be \"yes\" or \"no\".<|im_end|>\n<|im_start|>user\n"
# suffix = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
# prefix_tokens = tokenizer.encode(prefix, add_special_tokens=False)
# suffix_tokens = tokenizer.encode(suffix, add_special_tokens=False)
        
# task = 'Given a web search query, retrieve relevant passages that answer the query'

# queries = ["如何在 Milvus 中实现混合检索？",
#     "Explain gravity",
# ]

# documents = [
#     'Milvus 是一个高性能向量数据库。',
#     "Gravity is a force that attracts two bodies towards each other. It gives weight to physical objects and is responsible for the movement of planets around the sun.",
# ]

# pairs = [format_instruction(task, query, doc) for query, doc in zip(queries, documents)]

# # Tokenize the input texts
# inputs = process_inputs(pairs)
# scores = compute_logits(inputs)

# print("scores: ", scores)


# import torch
# import numpy as np
# from transformers import AutoTokenizer, AutoModelForCausalLM
# # from lsp.inference.server.helpers import auto_device

# # FYI links:
# #   Qwen3 paper w.r.t. Embedding and Reranking: https://arxiv.org/pdf/2506.05176
# #   hf repos:
# #      0.6B: https://huggingface.co/Qwen/Qwen3-Reranker-0.6B
# #      0.6B: https://huggingface.co/Qwen/Qwen3-Embedding-0.6B

# model_path = "/mnt/ddata2/models/Qwen3-Reranker-4B"
# tokenizer = AutoTokenizer.from_pretrained(model_path, padding_side='left')

# device = "cuda"
# if device == 'cuda':
#     # FYI this block exists largely to set best precision for a given device type
#     model_kwargs = dict(
#         torch_dtype=torch.float16,
#         # attn_implementation="flash_attention_2",  # cuda only
#         # only set device_map if using accelerate to shard
#         # device_map= {"": "cuda:0"},  # accelerate ONLY (also remove .to(device) below)
#         #
#         # notes re 6000 pro boot fiasco
#         # BTW when I dropped down to one GPU (6000 Pro RTX)... accelerate stopped placing properly (I did not check why) but it tried to put stuff on CPU too and blew up...
#         #   I fixed that by forcing first CUDA device
#         #   still weird that it was assuming there wasn't plenty of space when there was plenty of VRAM
#         #   is it possible accelerate's VRAM calcs are affected by disabled BAR size (bios fix to stop d4/d6 at boot)
#         #     so it sees the bar space only (which is default at like 256MB only?)
#     )
# else:
#     raise ValueError("ONLY setup for CUDA device")

# # remove .to(device) if using accelerate
# model = AutoModelForCausalLM.from_pretrained(model_path, **model_kwargs).to(device).eval()  # type: ignore

# # TODO! do some testing of re-ranker memory usage
# #  would it benefit from caching at all?
# #    i.e. when I re-rank the same query across multiple docs, is there a material boost from caching the query?
# #      IIRC query comes first in "prompt" so it would be cacheable
# #      FIM queries are long enough to matter for this
# #    PERHAPS decide request by request if you want to cache?
# #    - i.e. my Semantic Grep telescope picker the query is tiny so not much of a point there
# #    - FIM query is up to 1500 chars
# #    - MAYBE use len(query) to decide on caching?
# #  not sure it would but I suppose my search tool might benefit from it?
# #  but, before optimizing this here, let's test it first
# #  using realistic loads
# # model.config.use_cache = False
# # TODO! model.eval() too?

# #
# # FYI reranker uses probabilities from yes/no tokens for relevance score
# TOKEN_ID_NO = tokenizer.convert_tokens_to_ids("no")
# TOKEN_ID_YES = tokenizer.convert_tokens_to_ids("yes")
# #
# thread_prefix = "<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be \"yes\" or \"no\".<|im_end|>\n<|im_start|>user\n"
# thread_suffix = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
# thread_prefix_tokens = tokenizer.encode(thread_prefix, add_special_tokens=False)
# thread_suffix_tokens = tokenizer.encode(thread_suffix, add_special_tokens=False)
# max_length = 8192
# max_user_tokens = max_length - len(thread_prefix_tokens) - len(thread_suffix_tokens)

# def move_to_gpu(tensors, device):
#     for key in tensors:
#         tensors[key] = tensors[key].to(device)
#     return tensors

# def tokenize_docs(instruct: str, query: str, documents: list[str]):
#     if instruct is None or instruct.strip() == "":
#         raise ValueError("instruct must be provided")

#     # tokenize common prefix once:
#     instruct_query = f"<Instruct>: {instruct}\n<Query>: {query}\n<Document>: "
#     instruct_query_tokens = tokenizer.encode(instruct_query, add_special_tokens=False)

#     # NOTE layout is optimized for cache reuse! instruction/query are constant across a batch of documents
#     documents_tokens = tokenizer(
#         documents,
#         padding=False,
#         truncation='longest_first',
#         return_attention_mask=False,
#         max_length=max_user_tokens,
#     )
#     for i, doc_tokens in enumerate(documents_tokens['input_ids']):
#         # insert user message contents into the chat thread template (this way I don't have to tokenize the constant parts repeatedly
#         documents_tokens['input_ids'][i] = thread_prefix_tokens + instruct_query_tokens + doc_tokens + thread_suffix_tokens
#     documents_tokens = tokenizer.pad(documents_tokens, padding=True, return_tensors="pt", max_length=max_length)
#     return move_to_gpu(documents_tokens, model.device)

# def compute_relevance_scores(tokenized_inputs):
#     with torch.inference_mode():
#         output_logits = model(**tokenized_inputs).logits[:, -1, :]
#         yes_logits = output_logits[:, TOKEN_ID_YES]
#         no_logits = output_logits[:, TOKEN_ID_NO]
#         logits_no_and_yes = torch.stack([no_logits, yes_logits], dim=1)
#         # calculation to turn yes/no token logits into relevance score overall (per document)
#         log_softmax = torch.nn.functional.log_softmax(logits_no_and_yes, dim=1)
#         relevance_scores = log_softmax[:, 1].exp().tolist()
#         return relevance_scores

# def rerank(instruct: str, query: str, documents: list[str]) -> tuple[list[float], list[list[np.int64]]]:

#     # for now assume instruct and query are constant for all documents, if I need mixed batching then I can address that later...
#     # and actually I should encourage batching for same instruct/query else cache will be invalidated when instruct/query change

#     # TODO check for cancelation
#     tokenized_threads = tokenize_docs(instruct, query, documents)
#     # TODO check for cancellation before rerank
#     return compute_relevance_scores(tokenized_threads), tokenized_threads.input_ids.tolist()

# def main():
#     from numpy.testing import assert_array_almost_equal

#     # * test data
#     query1 = "What is the capital of China?"
#     query2 = "如何在 Milvus 中实现混合检索？"
#     documents = [
#         "The capital of China is Beijing.",
#         "Milvus 是一个高性能向量数据库。",
#     ]
#     instruct = 'Given a web search query, retrieve relevant passages that answer the query'

#     # * query1
#     actual_scores1, _ = rerank(instruct, query1, documents)
#     print("scores1: ", actual_scores1)
#     expected_scores1 = [0.99951171875, 5.066394805908203e-06]
#     # assert_array_almost_equal(actual_scores1, expected_scores1, decimal=3)

#     # * query2
#     actual_scores2, _ = rerank(instruct, query2, documents)
#     print("scores2: ", actual_scores2)
#     expected_scores2 = [4.947185516357422e-05, 0.99951171875]
#     # assert_array_almost_equal(actual_scores2, expected_scores2, decimal=3)
#     print("All tests passed")

# if __name__ == "__main__":
#     main()


# from langchain_community.document_loaders import UnstructuredHTMLLoader

# file_path = "/mnt/ddata2/cc007/omniknow2/parser/rag/3.5 代左控制器总成 ((拆卸和更换)).html"
# loader = UnstructuredHTMLLoader(file_path)
# data = loader.load()

# print(data)

from pymilvus import MilvusClient

client = MilvusClient(
    uri="http://localhost:19530",
    token="root:Milvus"
)

query_vector = [0.3580376395471989, -0.6023495712049978, 0.18414012509913835, -0.26286205330961354, 0.9029438446296592]

res = client.search(
    collection_name="my_collection",
    data=[query_vector],
    limit=5,
    filter='color like "red%" and likes > 50',
    output_fields=["color", "likes"]
)

for hits in res:
    print("TopK results:")
    for hit in hits:
        print(hit)


import requests
from PIL import Image
import os
import json
from typing import List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Literal
from uuid import uuid4
from datetime import datetime, timedelta


def is_image_ok(path: str) -> bool:
    try:
        with Image.open(path) as img:
            img.verify()   # 验证文件完整性
        return True
    except Exception:
        return False



def download_image(url: str, save_path: str):
    """
    下载图片到本地
    :param url: 图片 URL
    :param save_path: 保存的本地路径（含文件名）
    """
    # 创建目录
    os.makedirs(os.path.dirname(save_path), exist_ok=True)

    headers = {
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0"
    }

    try:
        with requests.get(url, headers=headers, stream=True, timeout=10) as r:
            r.raise_for_status()   # 检查状态码

            with open(save_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)

        # print(f"下载成功: {save_path}")
        # return save_path
    except Exception as e:
        print(f"下载失败: {e}")


def basic_check(path: str, min_size_mb=1):
    if not os.path.exists(path):
        return False, "文件不存在"
    size = os.path.getsize(path)
    if size < min_size_mb * 1024 * 1024:
        return False, f"文件过小：{size} bytes"
    return True


def check_video_header(path: str):
    with open(path, "rb") as f:
        header = f.read(16)

    # 常见视频文件头
    if header.startswith(b"\x00\x00\x00") or b"ftyp" in header:
        return True
    if header.startswith(b"\x1A\x45\xDF\xA3"):
        return True
    return False


import subprocess

def check_video_ffprobe(path: str):
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=codec_name,width,height",
        "-of", "default=noprint_wrappers=1",
        path
    ]
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except subprocess.CalledProcessError as e:
        return False


def check_video(save_path: str):

    ok = basic_check(save_path)
    if not ok:
        return False

    ok = check_video_header(save_path)
    if not ok:
        return False

    ok = check_video_ffprobe(save_path)
    if not ok:
        return False

    return True


class ChunkModel(BaseModel):
    """文档解析块返回类型"""
    chunk_id: str = Field(..., description="ID")
    content: str = Field(..., description="文字内容、图、表的capture")
    file_id: str = Field(..., description="文件ID")
    file_path: str = Field(..., description="文件路径")
    update_time: str = Field(..., description="更新时间")
    bbox_type: str = Field(default="text", description="边界框类型")
    title: str = Field(default="", description="文字的标题、图片表格的caption")
    summary: str = Field(default="", description="摘要")
    media_path: str = Field(default="", description="图片路径、视频路径、图纸路径")
    chunk_source: str = Field(default="", description="chunk的来源：document | image | video | audio | drawing | html")
    bbox: List[Any] = Field(default_factory=list, description="边界框坐标")
    page_idx: List[Any] = Field(default_factory=list, description="页码索引")
    others: Dict[str, Any] = Field(
        default_factory=dict,
        description="其他扩展字段"
    )

if __name__ == "__main__":

    root_dir = "/mnt/ddata2/cc007/omniknow2/parser/rag/tesla/outputs/source"
    chunks = []
    update_time = str(datetime.utcnow() + timedelta(hours=8))
    
    for file in os.listdir(root_dir):
        json_path = os.path.join(root_dir, file)
        # json_path = "/mnt/ddata2/cc007/omniknow2/parser/rag/tesla/outputs/source/驾驶位气囊线束总成 （（拆卸和更换））.json"
        if json_path.endswith(".json"):
            file_id = str(uuid4().hex)
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

                if len(data["text"])<50:
                    continue
                chunk_id = str(uuid4().hex)
                
                chunks.append(ChunkModel(
                    chunk_id=chunk_id,
                    content=data["text"],
                    title=data["title"],
                    file_id=file_id,
                    file_path=data["url"],
                    update_time=update_time,
                    bbox_type="text",
                    media_path=""
                ))
                
                for img_url in data["img"]:
                    save_path = os.path.join("/mnt/ddata2/cc007/omniknow2/parser/rag/tesla/outputs/media", f"{data["title"]}", f"{uuid4().hex}.jpg")
                    download_image(img_url, save_path)
                    if not is_image_ok(save_path):
                        continue
                        
                    chunk_id = str(uuid4().hex)
                    chunks.append(ChunkModel(
                        chunk_id=chunk_id,
                        content="",
                        title=data["title"],
                        file_id=file_id,
                        file_path=data["url"],
                        update_time=update_time,
                        bbox_type="image",
                        media_path=save_path
                    ))
                
                for img_url in data["video"]:
                    save_path = os.path.join("/mnt/ddata2/cc007/omniknow2/parser/rag/tesla/outputs/media", f"{data["title"]}", f"{uuid4().hex}.mp4")
                    download_image(img_url, save_path)
                    if not check_video(save_path):
                        continue
                        
                    chunk_id = str(uuid4().hex)
                    chunks.append(ChunkModel(
                        chunk_id=chunk_id,
                        content="",
                        title=data["title"],
                        file_id=file_id,
                        file_path=data["url"],
                        update_time=update_time,
                        bbox_type="video",
                        media_path=save_path
                    ))
        
        break                

    print(chunks)
    # download_image("https://service.tesla.cn/docs/Model3/ServiceManual/2024/media/M3_2024_GCSCD-2668_Driver_RemoveStep9.mp4", "/mnt/ddata2/cc007/omniknow2/parser/rag/000.mp4")
    # print(check_video("/mnt/ddata2/cc007/omniknow2/parser/rag/000.mp4"))
    
    # if not is_image_ok(save_path):
    #     print(f"图片损坏: {save_path}")
      
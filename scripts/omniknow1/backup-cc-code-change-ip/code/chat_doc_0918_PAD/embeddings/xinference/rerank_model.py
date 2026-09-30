from openai import OpenAI
from abc import ABC
import os
import numpy as np
import requests
import tiktoken

# tiktoken_cache_dir = os.path.join(os.path.dirname(__file__), "tiktoken_cache")
tiktoken_cache_dir = os.path.join('./', "tiktoken_cache")

os.environ["TIKTOKEN_CACHE_DIR"] = tiktoken_cache_dir
# encoder = tiktoken.encoding_for_model("gpt-3.5-turbo")
encoder = tiktoken.get_encoding("cl100k_base")
def sigmoid(x):
    return 1 / (1 + np.exp(-x))


def num_tokens_from_string(string: str) -> int:
    """Returns the number of tokens in a text string."""
    try:
        return len(encoder.encode(string))
    except Exception:
        return 0


def truncate(string: str, max_len: int) -> str:
    """Returns truncated text if the length of text exceed max_len."""
    return encoder.decode(encoder.encode(string)[:max_len])

class Base(ABC):
    def __init__(self, key, model_name):
        pass

    def similarity(self, query: str, texts: list):
        raise NotImplementedError("Please implement encode method!")

    def total_token_count(self, resp):
        try:
            return resp.usage.total_tokens
        except Exception:
            pass
        try:
            return resp["usage"]["total_tokens"]
        except Exception:
            pass
        return 0


class XInferenceRerank(Base):
    def __init__(self, key="xxxxxxx", model_name="", base_url=""):
        if base_url.find("/v1") == -1:
            base_url = os.path.join(base_url, "/v1/rerank")
        if base_url.find("/rerank") == -1:
            base_url = os.path.join(base_url, "/v1/rerank")
        self.model_name = model_name
        self.base_url = base_url
        self.headers = {
            "Content-Type": "application/json",
            "accept": "application/json",
            "Authorization": f"Bearer {key}"
        }

    def similarity(self, query: str, texts: list):
        if len(texts) == 0:
            return np.array([]), 0
        pairs = [(query, truncate(t, 4096)) for t in texts]
        token_count = 0
        for _, t in pairs:
            token_count += num_tokens_from_string(t)
        data = {
            "model": self.model_name,
            "query": query,
            "return_documents": "true",
            "return_len": "true",
            "documents": texts
        }
        res = requests.post(self.base_url, headers=self.headers, json=data).json()
        rank = np.zeros(len(texts), dtype=float)
        for d in res["results"]:
            rank[d["index"]] = d["relevance_score"]
        return rank, token_count


import json
class VllmRerank(Base):
    def __init__(self, key="xxxxxxx", model_name="", base_url=""):
        print(f"base_url: {base_url}")
        self.model_name = model_name
        self.base_url = base_url
        self.headers = {
            "Content-Type": "application/json",
            "accept": "application/json",
#            "Authorization": f"Bearer {key}"
        }

    def similarity(self, query: str, texts: list):
        if len(texts) == 0:
            return np.array([]), 0
        pairs = [(query, self.truncate(t, 6000)) for t in texts]
        truncated_texts = [self.truncate(t, 6000) for t in texts]
        token_count = 0
        for _, t in pairs:
            token_count += num_tokens_from_string(t)
        data = {
            "model": self.model_name,
            "query": query,
            "return_documents": True,
            "return_len": True,
#            "documents": truncated_texts
            "texts":truncated_texts
        }
        #print('self.base_url------------',self.base_url)
        #print('self.headers------------',self.headers)
        #print('data------------',data)
        res = requests.post(self.base_url, headers=self.headers, json=data).json()
#        print('********************',res)
        res.sort(key=lambda x: x["index"])

        #print(res)
        # print(res)
        rank = np.zeros(len(texts), dtype=float)
#        for d in res["results"]:
        for d in res:
            rank[d["index"]] = d["score"]
        return rank, token_count
    
    def truncate(self, string: str, max_len: int) -> str:
        """Returns truncated text if the length of text exceed max_len."""
        return encoder.decode(encoder.encode(string)[:max_len])


#if __name__ == "__main__":
#    rerank = VllmRerank(key="cc", model_name="bge-reranker-v2-m3", base_url="http://192.168.5.163:8106/v1/rerank")
#    print(rerank.similarity('nihao',['wohao','tahao']))

from openai import OpenAI
from abc import ABC
import os
import numpy as np
import tiktoken

tiktoken_cache_dir = os.path.join('./', "tiktoken_cache")

os.environ["TIKTOKEN_CACHE_DIR"] = tiktoken_cache_dir
# encoder = tiktoken.encoding_for_model("gpt-3.5-turbo")


class Base(ABC):
    def __init__(self, key, model_name):
        pass

    def encode(self, texts: list):
        raise NotImplementedError("Please implement encode method!")

    def encode_queries(self, text: str):
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


class XinferenceEmbed(Base):
    def __init__(self, key, model_name="", base_url=""):
        if base_url.split("/")[-1] != "v1":
            base_url = os.path.join(base_url, "v1")
        self.client = OpenAI(api_key=key, base_url=base_url)
        self.model_name = model_name

    def encode(self, texts: list):
        count = 0
        batch_size = 4  # batch=4,最多8G；batch=8,最多12G
        ress = []
        total_tokens = 0
        for i in range(0, len(texts), batch_size):
            if count%256 == 0:
                print(f"Processing {count} / {len(texts)}")
            res = self.client.embeddings.create(input=texts[i:i + batch_size], model=self.model_name)
            ress.extend([d.embedding for d in res.data])
            total_tokens += self.total_token_count(res)
            count += batch_size
        # return np.array(ress), total_tokens
        return ress, total_tokens

    def encode_queries(self, text):
        res = self.client.embeddings.create(input=[text],
                                            model=self.model_name)
        return np.array(res.data[0].embedding), self.total_token_count(res)


class VllmEmbed(Base):
    def __init__(self, key, model_name="", base_url=""):
        if base_url.split("/")[-1] != "v1":
            base_url = os.path.join(base_url, "v1")
        self.client = OpenAI(api_key=key, base_url=base_url)
        self.model_name = model_name
        self.encoding = tiktoken.get_encoding("cl100k_base")

    def encode(self, texts: list):
        count = 0
        batch_size = 1  # batch=4,最多8G；batch=8,最多12G
        ress = []
        total_tokens = 0

        # models = self.client.models.list()
        # print(models)
        # model  = models.data[0].id
        # print(model)
        # original_tokens = len(self.encoding.encode(texts[0]))
        # truncated_text = len(self.truncate_text(texts[0]))
        # print(original_tokens)  # 输出为37980
        # print(truncated_text)   # 输出为16422

        for i in range(0, len(texts), batch_size):
#            print('-------texts',texts)
            if count%batch_size == 0:
                print(f"Processing {count} / {len(texts)}")
            
            
            truncated_texts = [self.truncate_text(t) for t in texts[i:i + batch_size]]
            # for t in truncated_texts:
            #     token_len = len(self.encoding.encode(t))
            #     assert token_len <= 8192, f"Truncation failed: got {token_len} tokens"
            res = self.client.embeddings.create(input=truncated_texts, model=self.model_name)
            ress.extend([d.embedding for d in res.data])
            total_tokens += self.total_token_count(res)
            count += batch_size
            
            
        # return np.array(ress), total_tokens
        return ress, total_tokens
    
    def truncate_text(self, text: str, max_len: int=6000) -> str:
        """Returns truncated text if the length of text exceed max_len."""
        return self.encoding.decode(self.encoding.encode(text)[:max_len])
    

    # def truncate_text(self, text: str, max_tokens: int = 6000) -> str:
    #     """Returns truncated text if the token length exceeds max_tokens."""
    #     tokens = self.encoding.encode(text)
    #     # print('before',len(tokens))
    #     if len(tokens) > max_tokens:
    #         tokens = tokens[:max_tokens]
    #     # print('after',len(tokens))

    #     return self.encoding.decode(tokens)

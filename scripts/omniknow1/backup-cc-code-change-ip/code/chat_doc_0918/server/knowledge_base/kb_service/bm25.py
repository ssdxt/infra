#!/usr/bin/env python
from __future__ import annotations
import math
import numpy as np
from multiprocessing import Pool, cpu_count
from typing import Any, Callable, Dict, Iterable, List, Optional

from typing import Any, Callable, Dict, Iterable, List, Optional
import pickle
from langchain_core.callbacks import CallbackManagerForRetrieverRun
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from pydantic import ConfigDict, Field
import os

def default_preprocessing_func(text: str) -> List[str]:
    return text.split()


class BM25Retriever(BaseRetriever):
    """`BM25` retriever without Elasticsearch."""

    vectorizer: Any = None
    """ BM25 vectorizer."""
    docs: List[Document] = Field(repr=False)
    """ List of documents."""
    k: int = 4
    """ Number of documents to return."""
    preprocess_func: Callable[[str], List[str]] = default_preprocessing_func
    """ Preprocessing function to use on the text before BM25 vectorization."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
    )

    save_vectorizer_docs: Any = None

    @classmethod
    def from_texts(
        cls,
        texts: Iterable[str],
        metadatas: Optional[Iterable[dict]] = None,
        ids: Optional[Iterable[str]] = None,
        bm25_params: Optional[Dict[str, Any]] = None,
        preprocess_func: Callable[[str], List[str]] = default_preprocessing_func,
        **kwargs: Any,
    ) -> BM25Retriever:
        """
        Create a BM25Retriever from a list of texts.
        Args:
            texts: A list of texts to vectorize.
            metadatas: A list of metadata dicts to associate with each text.
            ids: A list of ids to associate with each text.
            bm25_params: Parameters to pass to the BM25 vectorizer.
            preprocess_func: A function to preprocess each text before vectorization.
            **kwargs: Any other arguments to pass to the retriever.

        Returns:
            A BM25Retriever instance.
        """
        # try:
        #     from rank_bm25 import BM25Okapi
        # except ImportError:
        #     raise ImportError(
        #         "Could not import rank_bm25, please install with `pip install "
        #         "rank_bm25`."
        #     )
        import time
        st = time.time()        
        texts_processed = [preprocess_func(t) for t in texts]
        bm25_params = bm25_params or {}
        # print('111111111111111',bm25_params)
        st1 = time.time()
        print("texts_processed cost time: ",st1-st)
        vectorizer = BM25Okapi(texts_processed, **bm25_params)
        print('BM25Okapi cost time: ', time.time()-st1)

        metadatas = metadatas or ({} for _ in texts)

        st2 = time.time()

        if ids:
            docs = [
                Document(page_content=t, metadata=m, id=i)
                for t, m, i in zip(texts, metadatas, ids)
            ]
        else:
            docs = [
                Document(page_content=t, metadata=m) for t, m in zip(texts, metadatas)
            ]
        
        save_dict = {
            "vectorizer": vectorizer if vectorizer else {},
            "docs": docs if vectorizer else {}
        }
        print('for cost time: ', time.time()-st2)
        
        
        return cls(
            vectorizer=vectorizer, docs=docs, preprocess_func=preprocess_func, save_vectorizer_docs=save_dict, **kwargs
        )
    
    def save_pth(self, name):
        if not self.save_vectorizer_docs:
            raise ValueError("No vectorizer and docs to save.")
        # with open(f'bm25_vectorizer_{name}.pkl', 'wb') as f:
        # 获取目录路径
        dir_path = os.path.dirname(name)

        # 如果目录不存在，则创建（包括父目录）
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path)
        with open(name, 'wb') as f:
            pickle.dump(self.save_vectorizer_docs, f)
        print(f"save pth file: {name}")

    
    @classmethod
    def load_pth(cls, file_path, preprocess_func, **kwargs: Any):
        with open(file_path, 'rb') as f:
            bm25_loaded = pickle.load(f)
    
        docs = bm25_loaded["docs"]
        vectorizer = bm25_loaded["vectorizer"]

        save_dict = {
            "vectorizer": vectorizer,
            "docs": docs
        }

        return cls(
            vectorizer=vectorizer, docs=docs, preprocess_func=preprocess_func, save_vectorizer_docs=save_dict, **kwargs
        )

    @classmethod
    def from_documents(
        cls,
        documents: Iterable[Document],
        *,
        bm25_params: Optional[Dict[str, Any]] = None,
        document_ids: Optional[Iterable[str]] = None,
        preprocess_func: Callable[[str], List[str]] = default_preprocessing_func,
        **kwargs: Any,
    ) -> BM25Retriever:
        """
        Create a BM25Retriever from a list of Documents.
        Args:
            documents: A list of Documents to vectorize.
            bm25_params: Parameters to pass to the BM25 vectorizer.
            preprocess_func: A function to preprocess each text before vectorization.
            **kwargs: Any other arguments to pass to the retriever.

        Returns:
            A BM25Retriever instance.
        """
        import time
        a = time.time()

        texts = []
        metadatas = []

        for d, chunk_ids in zip(documents,document_ids):
            texts.append(d.page_content)
            d.metadata["id"] = chunk_ids
            metadatas.append(d.metadata)

        if document_ids:
            ids = document_ids

        # texts, metadatas, ids = zip(
        #     *((d.page_content, d.metadata, d.metadata["vs_id"]) for d in documents)
        # )

        print('from_documents cost time',time.time()-a)

        return cls.from_texts(
            texts=texts,
            bm25_params=bm25_params,
            metadatas=metadatas,
            ids=ids,
            preprocess_func=preprocess_func,
            **kwargs,
        )


    def add_documents(self, new_documents: List[Document]):
        """Add new documents to the retriever."""
        new_texts = [d.page_content for d in new_documents]
        new_texts_processed = [self.preprocess_func(t) for t in new_texts]

        self.vectorizer.add(new_texts_processed)
        self.docs.extend(new_documents)
        self.save_vectorizer_docs = {
            "vectorizer": self.vectorizer,
            "docs": self.docs,
        }

    def delete_document_by_id(self, document_id: str):
        """Delete a document from the retriever by id."""
        for idx, doc in enumerate(self.docs):
            # print('self.doc----------------------', self.docs)
            if doc.metadata["id"] == document_id:
                self.vectorizer.delete(idx)
                self.docs.pop(idx)
                self.save_vectorizer_docs = {
                    "vectorizer": self.vectorizer,
                    "docs": self.docs,
                }
                return
        raise ValueError(f"Document id {document_id} not found.")

    def sync_state(self):
        self.save_vectorizer_docs = {
            "vectorizer": self.vectorizer,
            "docs": self.docs,
        }

    
    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> List[Document]:
        processed_query = self.preprocess_func(query)
        return_docs = self.vectorizer.get_top_n(processed_query, self.docs, n=self.k)
        return return_docs


class BM25:
    def __init__(self, corpus, tokenizer=None):
        self.corpus_size = 0
        self.avgdl = 0
        self.doc_freqs = []
        self.idf = {}
        self.doc_len = []
        self.tokenizer = tokenizer

        if tokenizer:
            corpus = self._tokenize_corpus(corpus)

        nd = self._initialize(corpus)
        self._calc_idf(nd)

    def _initialize(self, corpus):
        nd = {}  # word -> number of documents with word
        num_doc = 0
        for document in corpus:
            self.doc_len.append(len(document))
            num_doc += len(document)

            frequencies = {}
            for word in document:
                if word not in frequencies:
                    frequencies[word] = 0
                frequencies[word] += 1
            self.doc_freqs.append(frequencies)

            for word, freq in frequencies.items():
                try:
                    nd[word]+=1
                except KeyError:
                    nd[word] = 1

            self.corpus_size += 1

        self.avgdl = num_doc / self.corpus_size
        return nd

    def _tokenize_corpus(self, corpus):
        pool = Pool(cpu_count())
        tokenized_corpus = pool.map(self.tokenizer, corpus)
        return tokenized_corpus

    def _calc_idf(self, nd):
        raise NotImplementedError()

    def get_scores(self, query):
        raise NotImplementedError()

    def get_batch_scores(self, query, doc_ids):
        raise NotImplementedError()

    def get_top_n(self, query, documents, n=5):
        # print('--------chunk总数量为：----------',self.corpus_size)
        assert self.corpus_size == len(documents), "The documents given don't match the index corpus!"

        scores = self.get_scores(query)
        top_n = np.argsort(scores)[::-1][:n]
        return [documents[i] for i in top_n]


class BM25Okapi(BM25):
    # def __init__(self, corpus, tokenizer=None, k1=1.5, b=0.75, epsilon=0.25):
    def __init__(self, corpus, tokenizer=None, k1=1.2, b=0.75, epsilon=0.25):
        self.k1 = k1
        self.b = b
        self.epsilon = epsilon
        super().__init__(corpus, tokenizer)

    def _calc_idf(self, nd):
        """
        Calculates frequencies of terms in documents and in corpus.
        This algorithm sets a floor on the idf values to eps * average_idf
        """
        # collect idf sum to calculate an average idf for epsilon value
        idf_sum = 0
        # collect words with negative idf to set them a special epsilon value.
        # idf can be negative if word is contained in more than half of documents
        negative_idfs = []
        for word, freq in nd.items():
            idf = math.log(self.corpus_size - freq + 0.5) - math.log(freq + 0.5)
            self.idf[word] = idf
            idf_sum += idf
            if idf < 0:
                negative_idfs.append(word)
        self.average_idf = idf_sum / len(self.idf)

        eps = self.epsilon * self.average_idf
        for word in negative_idfs:
            self.idf[word] = eps

    def get_scores(self, query):
        """
        The ATIRE BM25 variant uses an idf function which uses a log(idf) score. To prevent negative idf scores,
        this algorithm also adds a floor to the idf value of epsilon.
        See [Trotman, A., X. Jia, M. Crane, Towards an Efficient and Effective Search Engine] for more info
        :param query:
        :return:
        """
        score = np.zeros(self.corpus_size)
        doc_len = np.array(self.doc_len)
        for q in query:
            q_freq = np.array([(doc.get(q) or 0) for doc in self.doc_freqs])
            score += (self.idf.get(q) or 0) * (q_freq * (self.k1 + 1) /
                                               (q_freq + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)))
        
        # for i in score:
        #     print('---------score-----------', i)
        return score

    def get_batch_scores(self, query, doc_ids):
        """
        Calculate bm25 scores between query and subset of all docs
        """
        assert all(di < len(self.doc_freqs) for di in doc_ids)
        score = np.zeros(len(doc_ids))
        doc_len = np.array(self.doc_len)[doc_ids]
        for q in query:
            q_freq = np.array([(self.doc_freqs[di].get(q) or 0) for di in doc_ids])
            score += (self.idf.get(q) or 0) * (q_freq * (self.k1 + 1) /
                                               (q_freq + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)))
        return score.tolist()
    

    def add(self, documents: List[List[str]]):
        """Add preprocessed documents to BM25 index."""
        nd = {}
        for document in documents:
            self.doc_len.append(len(document))
            frequencies = {}
            for word in document:
                if word not in frequencies:
                    frequencies[word] = 0
                frequencies[word] += 1
            self.doc_freqs.append(frequencies)

            for word in frequencies:
                nd[word] = nd.get(word, 0) + 1

            self.corpus_size += 1
        
        self._recalculate_idf(nd)

    def delete(self, index: int):
        """Delete a document from BM25 index by index."""
        if index >= self.corpus_size:
            raise IndexError("Document index out of range")

        removed_doc = self.doc_freqs.pop(index)
        removed_len = self.doc_len.pop(index)
        self.corpus_size -= 1

        for word in removed_doc:
            # 逐词更新df统计
            count = 0
            for doc in self.doc_freqs:
                if word in doc:
                    count += 1
            if count == 0:
                self.idf.pop(word, None)
            else:
                self.idf[word] = math.log(self.corpus_size - count + 0.5) - math.log(count + 0.5)

        self.avgdl = sum(self.doc_len) / self.corpus_size if self.corpus_size > 0 else 0

    def _recalculate_idf(self, nd):
        """Recalculate idf after adding documents"""
        # 只基于增量的词刷新idf
        idf_sum = sum(self.idf.values())
        for word, freq in nd.items():
            total_freq = 0
            for doc in self.doc_freqs:
                if word in doc:
                    total_freq += 1
            idf = math.log(self.corpus_size - total_freq + 0.5) - math.log(total_freq + 0.5)
            self.idf[word] = idf
            idf_sum += idf

        self.average_idf = idf_sum / len(self.idf) if self.idf else 0

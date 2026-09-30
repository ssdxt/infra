# -*- coding: utf-8 -*-
"""file_doc.doc_id 回填 / 校验工具（配合 fix_doc_id.sh 使用）

【问题背景】
  /knowledge_base/parse_docs 解析阶段会向 file_doc 表写入文本块，此时 doc_id 为 NULL。
  随后向量化阶段 base.add_doc() -> update_file_to_db() -> update_docs_in_db() 负责把
  向量库生成的 id 回填到 file_doc.doc_id。

  旧版 update_docs_in_db() 用「metadata 的 key 集合完全相等」来定位记录：
      set(metadata.keys()) == set(db_metadata.keys())
  但向量化时 embed_documents() 会给 doc.metadata 追加一个 "id" 键，
  而 DB 里存的是解析阶段、尚未追加 "id" 的 metadata（少一个键）。
  于是 35 条记录全部匹配失败，打印 35 次「未找到匹配的记录，无法更新 doc_id」，
  doc_id 永远为 NULL。

  后果：KBService.list_docs() 拿 doc_id=NULL 调 get_doc_by_id(None)，全部返回 None，
  list_docs() 返回 []，于是 /train/generate_test_cases 判为「未找到文档块」，
  把 knowledge_file.qa_status 置为「失败」——前端看到的就是「问答对生成失败」。

【本工具原理】
  向量库落盘在 knowledge_base/<kb>/vector_store/<embed_model>/index.pkl，
  pickle 内容为 (InMemoryDocstore, index_to_docstore_id)；
  docstore._dict 的 key 即为 doc_id 应有的值，key -> Document 一一对应。
  把 file_doc.page_content 与 Document.page_content 对齐即可回填 doc_id。

  匹配优先级（要求唯一命中，否则记为 unresolved 不写库）：
    1) page_content 完全相同
    2) page_content 前 512 字符相同（column 为 String(2048)，可能被截断）
    3) DB metadata 的键值对是向量库 metadata 的子集（键值全等）

【用法】见 fix_doc_id.sh
"""

import io
import json
import os
import pickle
import sys
import time

import pymysql

PROJECT_DIR = "/deploy/code/chat_doc_0918"
KB_ROOT = os.path.join(PROJECT_DIR, "knowledge_base")
LOG_DIR = "/deploy/cc/logs"
DB_CONF = dict(host="192.168.21.111", port=2881, user="root@test",
               password="12345", database="chat_doc", charset="utf8mb4")
PREFIX_LEN = 512


def connect():
    return pymysql.connect(**DB_CONF)


def list_kbs(cur, kb_name=None):
    """返回 [(kb_name, embed_model), ...]"""
    cur.execute("select * from knowledge_base")
    cols = [d[0].lower() for d in cur.description]
    idx_name = cols.index("kb_name")
    idx_emb = cols.index("embed_model") if "embed_model" in cols else None
    if idx_emb is None:
        for cand in ("embedding_model", "vs_type", "embed_model_name"):
            if cand in cols:
                idx_emb = cols.index(cand)
                break
    out = []
    for row in cur.fetchall():
        name = row[idx_name]
        if kb_name and name != kb_name:
            continue
        out.append((name, row[idx_emb] if idx_emb is not None else None))
    return out


def find_index_pkl(kb_name, embed_model):
    """定位向量库 index.pkl，返回 (path, docstore_dict)"""
    if embed_model:
        p = os.path.join(KB_ROOT, kb_name, "vector_store", embed_model, "index.pkl")
        if os.path.exists(p):
            return p, load_docstore(p)
    vs_dir = os.path.join(KB_ROOT, kb_name, "vector_store")
    if os.path.isdir(vs_dir):
        for sub in sorted(os.listdir(vs_dir)):
            p = os.path.join(vs_dir, sub, "index.pkl")
            if os.path.exists(p):
                return p, load_docstore(p)
    return None, None


def load_docstore(path):
    raw = pickle.load(io.open(path, "rb"))
    ds = raw[0] if isinstance(raw, (tuple, list)) else raw
    return dict(ds._dict)


def build_indexes(docstore):
    """构建三种匹配索引: 内容 -> [id], 前缀 -> [id], metadata tuple -> [id]"""
    by_content = {}
    by_prefix = {}
    by_meta = {}
    for doc_id, doc in docstore.items():
        content = doc.page_content or ""
        by_content.setdefault(content, []).append(doc_id)
        by_prefix.setdefault(content[:PREFIX_LEN], []).append(doc_id)
        md = doc.metadata or {}
        try:
            key = tuple(sorted((k, json.dumps(v, sort_keys=True, ensure_ascii=False))
                               for k, v in md.items()))
        except Exception:
            key = None
        if key is not None:
            by_meta.setdefault(key, []).append(doc_id)
    return by_content, by_prefix, by_meta


def resolve(db_md, content, by_content, by_prefix, by_meta):
    """返回 (doc_id, how) —— 未唯一命中则 (None, reason)"""
    if content is None:
        content = ""
    hit = by_content.get(content)
    if hit and len(hit) == 1:
        return hit[0], "content"
    if content and len(content) >= PREFIX_LEN:
        hit = by_prefix.get(content[:PREFIX_LEN])
        if hit and len(hit) == 1:
            return hit[0], "prefix"
    if isinstance(db_md, str):
        try:
            db_md = json.loads(db_md)
        except Exception:
            db_md = {}
    if isinstance(db_md, dict) and db_md:
        key = tuple(sorted((k, json.dumps(db_md[k], sort_keys=True, ensure_ascii=False))
                           for k in db_md))
        hit = by_meta.get(key)
        if hit and len(hit) == 1:
            return hit[0], "meta"
        return None, "no-match"
    return None, "no-match"


def fetch_rows(cur, kb_name):
    cur.execute("select id, file_name, doc_id, meta_data, page_content "
                "from file_doc where kb_name=%s order by id", (kb_name,))
    return cur.fetchall()


def cmd_diag(kb_name=None):
    conn = connect()
    cur = conn.cursor()
    print("%-38s %6s %6s %6s  %s" % ("KB", "TOTAL", "NULL", "MISS", "INDEX"))
    for name, emb in list_kbs(cur, kb_name):
        rows = fetch_rows(cur, name)
        nulls = [r for r in rows if r[2] is None]
        path, ds = find_index_pkl(name, emb)
        miss = 0
        if ds is None:
            miss = len(nulls)
            mark = "NO-INDEX(%s)" % (path or "-")
        else:
            bi, bp, bm = build_indexes(ds)
            for r in nulls:
                if resolve(r[3], r[4], bi, bp, bm)[0] is None:
                    miss += 1
            mark = "%d docs (vs=%s)" % (len(ds), emb)
        print("%-38s %6d %6d %6d  %s" % (name[:38], len(rows), len(nulls), miss, mark))
    conn.close()


def cmd_fix(kb_name=None, apply=False):
    conn = connect()
    cur = conn.cursor()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    if not os.path.isdir(LOG_DIR):
        os.makedirs(LOG_DIR)
    for name, emb in list_kbs(cur, kb_name):
        rows = fetch_rows(cur, name)
        nulls = [r for r in rows if r[2] is None]
        if not nulls:
            print("[%s] nothing to do (no NULL doc_id)" % name)
            continue
        path, ds = find_index_pkl(name, emb)
        if ds is None:
            print("[%s] SKIP: vector store index.pkl not found (%s)" % (name, path))
            continue
        bi, bp, bm = build_indexes(ds)
        changes = []
        hows = {}
        unresolved = []
        for r in nulls:
            doc_id, how = resolve(r[3], r[4], bi, bp, bm)
            if doc_id is None:
                unresolved.append(r[0])
                continue
            changes.append({"row_id": r[0], "file_name": r[1],
                            "old_doc_id": r[2], "new_doc_id": doc_id})
            hows[how] = hows.get(how, 0) + 1
        print("[%s] NULL=%d  resolved=%d %s  unresolved=%d"
              % (name, len(nulls), len(changes), hows, len(unresolved)))
        if unresolved:
            print("      unresolved row ids: %s" % unresolved[:20])
        if not changes:
            continue
        if not apply:
            print("      (dry-run, use 'fix --apply' to write)")
            continue
        rec = os.path.join(LOG_DIR, "fix_doc_id_%s_%s.json" % (name, stamp))
        io.open(rec, "w", encoding="utf-8").write(
            json.dumps({"kb_name": name, "index_pkl": path, "changes": changes},
                       ensure_ascii=False, indent=2))
        for c in changes:
            cur.execute("update file_doc set doc_id=%s where id=%s and doc_id is null",
                        (c["new_doc_id"], c["row_id"]))
        conn.commit()
        print("      applied %d rows, rollback file: %s" % (len(changes), rec))
    conn.close()


def cmd_verify(kb_name=None):
    conn = connect()
    cur = conn.cursor()
    for name, emb in list_kbs(cur, kb_name):
        rows = fetch_rows(cur, name)
        nulls = [r for r in rows if r[2] is None]
        path, ds = find_index_pkl(name, emb)
        ok = None
        if ds is not None:
            ids = set(ds.keys())
            ok = sum(1 for r in rows if r[2] in ids)
        print("[%s] rows=%d  doc_id NULL=%d  doc_id 命中向量库=%s  vs=%s"
              % (name, len(rows), len(nulls), ok, len(ds) if ds else "NO-INDEX"))
        # list_docs 等价校验：统计能被 get_doc_by_id 取回的行数
        if ds is not None:
            good = sum(1 for r in rows if r[2] in ds)
            print("      list_docs() 将返回 %d / %d 个 Document" % (good, len(rows)))
    conn.close()


def cmd_rollback(kb_name=None, rec_file=None):
    files = []
    if rec_file:
        files = [rec_file]
    else:
        for f in sorted(os.listdir(LOG_DIR)):
            if f.startswith("fix_doc_id_") and f.endswith(".json"):
                if kb_name and not f.startswith("fix_doc_id_%s_" % kb_name):
                    continue
                files.append(os.path.join(LOG_DIR, f))
    if not files:
        print("no rollback record found in %s" % LOG_DIR)
        return
    f = files[-1]
    data = json.loads(io.open(f, encoding="utf-8").read())
    conn = connect()
    cur = conn.cursor()
    for c in data["changes"]:
        cur.execute("update file_doc set doc_id=%s where id=%s",
                    (c["old_doc_id"], c["row_id"]))
    conn.commit()
    conn.close()
    print("rolled back %d rows of kb=%s from %s" % (len(data["changes"]), data["kb_name"], f))


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "diag"
    kb = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("-") else None
    apply = "--apply" in sys.argv
    if mode == "diag":
        cmd_diag(kb)
    elif mode == "fix":
        cmd_fix(kb, apply)
    elif mode == "verify":
        cmd_verify(kb)
    elif mode == "rollback":
        cmd_rollback(kb, sys.argv[3] if len(sys.argv) > 3 else None)
    else:
        print("usage: fix_doc_id.py diag|fix|verify|rollback [kb_name] [--apply]")
        sys.exit(2)

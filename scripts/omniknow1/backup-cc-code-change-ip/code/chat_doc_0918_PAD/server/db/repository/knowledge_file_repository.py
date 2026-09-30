from server.db.models.knowledge_base_model import KnowledgeBaseModel
from server.db.models.knowledge_file_model import KnowledgeFileModel, FileDocModel
from server.db.session import with_session
from server.knowledge_base.utils import KnowledgeFile
from typing import List, Dict
from sqlalchemy import inspect,text

@with_session
def delete_tc_by_kbfile(session, kb_name: str, file_name: str = None) -> Dict:
    """
    删除与知识库和文件相关的 test_case 和 test_history 记录
    """

    # 删除与 test_case 相关的 test_history
    sql_delete_history = '''
    DELETE FROM test_history 
    WHERE test_case_id IN (
        SELECT id FROM test_case WHERE vs_id IN (
            SELECT doc_id FROM file_doc WHERE kb_name = :kb_name
    '''
    
    if file_name:
        sql_delete_history += ' AND file_name = :file_name'
    
    sql_delete_history += '))'

    params = {"kb_name": kb_name}
    if file_name:
        params["file_name"] = file_name

    session.execute(text(sql_delete_history), params)

    # 删除 test_case
    sql_delete_case = '''
    DELETE FROM test_case 
    WHERE vs_id IN (
        SELECT doc_id FROM file_doc WHERE kb_name = :kb_name
    '''
    
    if file_name:
        sql_delete_case += ' AND file_name = :file_name'
    
    sql_delete_case += ')'

    session.execute(text(sql_delete_case), params)

    session.commit()
    
    return {"code": 0, "msg": "删除完成"}



@with_session
def delete_tc_by_vs(session, vs_id: str) -> Dict:
    """
    批量删除与指定 vs_id 相关的 test_case 和 test_history 数据
    """
    # 删除与 test_case 相关的 test_history
    sql_delete_history = '''
    DELETE FROM test_history 
    WHERE test_case_id IN (
        SELECT id FROM test_case WHERE vs_id = :vs_id
    )
    '''
    params = {"vs_id": vs_id}
    
    session.execute(text(sql_delete_history), params)

    # 删除 test_case
    sql_delete_case = '''
    DELETE FROM test_case 
    WHERE vs_id = :vs_id
    '''

    session.execute(text(sql_delete_case), params)
    session.commit()

    return {"code": 0, "msg": "删除成功"}

@with_session
def list_docs_from_db(session,
                      kb_name: str,
                      file_name: str = None,
                      metadata: Dict = {},
                      ) -> List[Dict]:
    '''
    列出某知识库某文件对应的所有Document。
    返回形式：[{"id": str, "metadata": dict}, ...]
    '''

    docs = session.query(FileDocModel).filter_by(kb_name=kb_name)
    # print("docs",docs)
    if file_name:
        docs = docs.filter_by(file_name=file_name)
    for k, v in metadata.items():
        docs = docs.filter(FileDocModel.meta_data[k].as_string()==str(v))

    result=  [{"id": x.doc_id, "metadata": x.metadata} for x in docs.all()]

    return result        

    # for r in result:
    #     vs_id = r["id"]
    #     # {"code":0,"msg":"成功","data":{"count":count,"test_cases":data}}
    #     test_cases = test_case_list(course_id=None,vs_id=vs_id)["data"]
    #     print(test_cases,test_cases)
    #     test_cases =test_cases.get("test_cases")
    #     _testcases = [{"test_case_id",x["test_case_id"],"question",x["question"],"answer",x["answer"]} for x in test_case_list]
    #     r.metadata["test_cases"] = _testcases

@with_session
def delete_docs_from_db(session,
                      kb_name: str,
                      file_name: str = None,
                      doc_id:str = None
                      ) -> List[Dict]:
    '''
    删除某知识库某文件对应的所有Document，并返回被删除的Document。
    返回形式：[{"id": str, "metadata": dict}, ...]
    '''
    # docs = list_docs_from_db(kb_name=kb_name, file_name=file_name)
    query = session.query(FileDocModel).filter_by(kb_name=kb_name)
    if file_name:
        query = query.filter_by(file_name=file_name)
    # print("kb_name",kb_name)
    # print("doc_id",doc_id)
    # print("file_name",file_name)
    if doc_id:
        query = query.filter_by(doc_id=doc_id)
    temp = query.all()
    for t in temp:
        print("t.doc_id",t.doc_id) 
    status = query.delete()
    session.commit()
    # print("status",status)
    return status

@with_session
def update_docs_in_db(session,
                      kb_name: str,
                      file_name: str,
                      doc_infos: List[Dict]):
    """
    根据kb_name, file_name和meta_data找到对应记录并更新doc_id。
    doc_infos格式：[{"id": str, "metadata": dict}, ...]
    """
    if not doc_infos:
        print("输入的doc_infos参数为空")
        return False
    
    all_records = session.query(FileDocModel).filter_by(
        kb_name=kb_name,
        file_name=file_name
    ).all()
    
    for d in doc_infos:
        metadata = d['metadata']
        
        # 使用手动比较方式查找匹配记录
        existing_doc = None
        for record in all_records:
            db_metadata = record.meta_data
            
            # 检查键和值是否完全匹配
            if (all(key in metadata for key in db_metadata.keys()) and
                all(metadata[key] == db_metadata[key] for key in db_metadata.keys())):
                existing_doc = record
                break
        
        if existing_doc:
            existing_doc.doc_id = d["id"]
            all_records.remove(existing_doc)
        else:
            print(f"未找到匹配的记录，无法更新 doc_id")

    session.commit()
    return True

@with_session
def list_filedoc_from_db(session,kb_name:str,file_name:str):
    db_objs = session.query(FileDocModel).filter_by(kb_name=kb_name, file_name=file_name).all()
    if db_objs is None:
        return {"code":-1,"msg":"数据不存在","data":{}}
    data =[db_obj.to_out_dict() for db_obj in  db_objs]

    return {"code":0,"msg":"成功","data":data}

@with_session
def get_filedoc_by_doc_id(session, vs_id: str):
    db_obj = session.query(FileDocModel).filter_by(doc_id=vs_id).first()
    if db_obj is None:
        return {"code": -1, "msg": "数据不存在", "data": {}}
    
    return {"code": 0, "msg": "成功", "data": db_obj.to_out_dict()}


from langchain.docstore.document import Document

@with_session
def add_parsed_docs_to_db(session,
                          kb_name: str,
                          file_name: str,
                          documents: List[Document]):
    """
    将解析后的文档（未向量化）存储到数据库。
    """
    if not documents:
        print("解析后的文档块信息为空")
        return False
    
    existing_docs = session.query(FileDocModel).filter_by(kb_name=kb_name, file_name=file_name).all()

    # 如果现有记录存在，检查doc_id情况
    if existing_docs:
        existing_docs_with_id = [doc for doc in existing_docs if doc.doc_id is not None]
        
        # 没有doc_id的记录，直接删除
        if not existing_docs_with_id:
            for doc in existing_docs:
                session.delete(doc)
        
        # 如果所有现有记录都有doc_id，进行对比
        else:
            # 如果数量不一致，删除现有记录
            # if len(existing_docs_with_id) == len(documents):
            delete_tc_by_kbfile(kb_name,file_name)
            update_qa_status(kb_name, file_name, "未生成")
            update_qa_count(kb_name, file_name, 0)
            for doc in existing_docs:
                session.delete(doc)
        
            # else:
            #     # 如果数量一致，逐条对比内容
            #     is_same = all(
            #         existing_doc.page_content == doc.page_content
            #         for existing_doc, doc in zip(existing_docs_with_id, documents)
            #     )
            #     # 如果内容不一致，删除现有记录
            #     if not is_same:
            #         delete_tc_by_kbfile(kb_name,file_name)
            #         update_qa_status(kb_name, file_name, "未生成")
            #         update_qa_count(kb_name, file_name, 0)
            #         for doc in existing_docs:
            #             session.delete(doc)
            #     else:
                    # 内容一致，无需更新
                    # return True

    for doc in documents:
        obj = FileDocModel(
            kb_name=kb_name,
            file_name=file_name,
            doc_id=None,
            meta_data=doc.metadata,
            page_content=doc.page_content
        )
        session.add(obj)

    session.commit()
    return True

@with_session
def add_abstract_to_db(session, kb_name: str, file_name: str, abstract: List[dict]):
    for item in abstract:
        titles = item.get("titles", "")
        page_content = item.get("page_content", "")
    
        doc = FileDocModel(
            kb_name=kb_name,
            file_name=file_name,
            doc_id=None,
            meta_data={"titles": titles},
            page_content=page_content
        )

        session.add(doc)
    session.commit()
    return True

@with_session
def get_parsed_docs_from_db(session, kb_name: str, file_name: str) -> List[Document]:
    """
    从数据库中提取解析后的文档，并重新拼装成Document对象列表。
    """
    # 查询数据库中对应的文档记录
    records = session.query(FileDocModel).filter_by(kb_name=kb_name, file_name=file_name).all()
    
    if not records:
        print(f"未找到知识库 {kb_name} 中文件 {file_name} 的解析文档记录")
        return []

    documents = [
        Document(page_content=record.page_content, metadata=record.meta_data)
        for record in records
    ]

    return documents


@with_session
def update_docs_to_db(session,
                   kb_name: str,
                   file_name: str,
                   doc_infos: List[Dict]):
    '''
    将某知识库某文件对应的所有Document信息添加到数据库。
    doc_infos形式：[{"id": str, "metadata": dict}, ...]
    '''
    #! 这里会出现doc_infos为None的情况，需要进一步排查
    if doc_infos is None:
        return False
    for d in doc_infos:
        doc = session.query(FileDocModel).filter_by(kb_name=kb_name)
        if file_name:
            doc = doc.filter_by(file_name=file_name)
        
        page_content = d["page_content"]
        metadata = d["metadata"]
        vs_id = d["metadata"]["vs_id"]

        if vs_id:
            doc = doc.filter_by(doc_id=vs_id)
        
        res = doc.update({FileDocModel.meta_data: metadata,FileDocModel.page_content: page_content}, synchronize_session="fetch")
        print("res",res)
    session.commit()
    return True

@with_session
def get_docs_detail(session, kb_name: str, filename: str) -> dict:
    """
    获取指定知识库和文件名对应的文档块详情
    """
    docs = session.query(FileDocModel).filter_by(kb_name=kb_name,file_name=filename).all()

    if docs:
        return [
            {
                "doc_id": doc.doc_id,
                "metadata": doc.meta_data,
                "page_content": doc.page_content
            }
            for doc in docs
        ]
    else:
        return []
    
@with_session
def count_files_from_db(session, kb_name: str) -> int:
    return session.query(KnowledgeFileModel).filter_by(kb_name=kb_name).count()


@with_session
def list_files_from_db(session, kb_name, file_name=None, parse_status=None, page_start=None, page_end=None):

    files = session.query(KnowledgeFileModel)
    
    if kb_name:
        files = files.filter_by(kb_name=kb_name)
    if file_name:
        files = files.filter(KnowledgeFileModel.file_name.like('%'+file_name+'%'))
    if parse_status:
        files = files.filter_by(parse_status=parse_status)
    
    files = files.order_by(KnowledgeFileModel.id.desc())
    count=len(files.all())

    if page_start is not None and page_end is not None:
        files = files.slice(page_start,page_end).all()
    else:
        files = files.all()
    # docs = [f.file_name for f in files]
    data = [file.to_out_dict() for file in files]

    return {"code":0,"msg":"成功","data":{"count":count,"files":data}}
 


@with_session
def add_file_to_db(session,
                   kb_file: KnowledgeFile,
                   custom_docs: bool = False
                   ):
    """
    将文件信息添加或更新到数据库
    """
    # 查找对应的知识库
    kb = session.query(KnowledgeBaseModel).filter_by(kb_name=kb_file.kb_name).first()
    if kb:
        # 获取文件的修改时间和大小
        mtime = kb_file.get_mtime()
        size = kb_file.get_size()
        default_file_parse_configs = {
            "image_save": True,
            "generate_query": True,
            "key_words": [],
            "separators": "W1siXuesrFxccyooPzpb5LiA5LqM5LiJ5Zub5LqU5YWt5LiD5YWr5Lmd5Y2BXXsxLDJ9fFxcZCspXFxzKlvnq6BdIiwi6ZmEXFxzKuW9lSIsIl7lj4JcXHMq6ICDXFxzKuaWh1xccyrnjK4iLCJe6ZmE6KGoXFxzKyJdLFsiXuesrFxccyooPzpb5LiA5LqM5LiJ5Zub5LqU5YWt5LiD5YWr5Lmd5Y2BXXsxLDJ9fFxcZCspXFxzKlvoioJdIiwiXumZhFxccyrlvZVcXHMqW0EtWl0iXSxbIl5cXGQrXFxzIl0sWyJeXFxkKyhcXC5cXGQrKXsxfVxccyJdLFsiXlxcZCsoXFwuXFxkKyl7Mn1cXHMiXSxbIl5cXGQrKFxcLlxcZCspezN9XFxzIl0sWyJeXFxkKyhcXC5cXGQrKXs0fVxccyJdXQ=="
        }

        # 检查文件是否已经存在于数据库
        existing_file: KnowledgeFileModel = (session.query(KnowledgeFileModel)
                                             .filter_by(file_name=kb_file.filename,
                                                        kb_name=kb_file.kb_name)
                                             .first())

        if existing_file:
            # 如果文件已经存在，更新相关信息和版本号
            existing_file.file_mtime = mtime
            existing_file.file_size = size
            existing_file.custom_docs = custom_docs
            existing_file.file_version += 1

        else:
            # 如果文件不存在，创建新的文件记录
            new_file = KnowledgeFileModel(
                file_name=kb_file.filename,
                file_ext=kb_file.ext,
                kb_name=kb_file.kb_name,
                document_loader_name=kb_file.document_loader_name,
                text_splitter_name=kb_file.text_splitter_name or "SpacyTextSplitter",
                file_mtime=mtime,
                file_size=size,
                custom_docs=custom_docs,
                docs_count=0,
                qa_status='未生成',
                qa_count=0,
                parse_status='未解析',
                file_parse_configs=default_file_parse_configs
            )
            kb.file_count += 1
            session.add(new_file)

    return True

@with_session
def add_parsed_file_to_db(session,
                          kb_name: str,
                          file_name: str,
                          documents: List[Document]):
    
    kb = session.query(KnowledgeBaseModel).filter_by(kb_name=kb_name).first()
    if kb:
        # 如果已经存在该文件，则更新文件信息
        existing_file: KnowledgeFileModel = (session.query(KnowledgeFileModel)
                                             .filter_by(file_name=file_name,
                                                        kb_name=kb_name)
                                            .first())
        if existing_file:
            existing_file.docs_count = len(documents)

        session.commit()
        add_parsed_docs_to_db(kb_name=kb_name, file_name=file_name, documents=documents)
    return True

@with_session
def update_parsed_file_to_db(session,
                kb_file: KnowledgeFile
                ):
    
    # print(kb_file.splited_docs)
    # print(len(kb_file.splited_docs))
    kb = session.query(KnowledgeBaseModel).filter_by(kb_name=kb_file.kb_name).first()
    if kb:
        # 如果已经存在该文件，则更新文件信息
        existing_file: KnowledgeFileModel = (session.query(KnowledgeFileModel)
                                             .filter_by(file_name=kb_file.filename,
                                                        kb_name=kb_file.kb_name)
                                            .first())

        if existing_file:
            existing_file.docs_count = len(kb_file.splited_docs)
        
        session.commit()
        add_parsed_docs_to_db(kb_name=kb_file.kb_name, file_name=kb_file.filename, documents=kb_file.splited_docs)
    return True

@with_session
def update_parse_status(session, kb_name: str, file_name: str, status: str):
    """
    更新文件的解析状态
    """
    file = session.query(KnowledgeFileModel).filter_by(kb_name=kb_name, file_name=file_name).first()
    if file:
        file.parse_status = status

    session.commit()
    return True

@with_session
def update_qa_status(session, kb_name: str, file_name: str, status: str):
    """
    更新文件的问答对生成状态
    """
    file = session.query(KnowledgeFileModel).filter_by(kb_name=kb_name, file_name=file_name).first()
    if file is None:
        return {"code":-1,"msg":"数据不存在","data":{}}
    if file:
        file.qa_status = status

    session.commit()
    return True

@with_session
def update_qa_count(session, kb_name: str, file_name: str, count: int):
    """
    更新文件的问答对生成状态
    """
    file = session.query(KnowledgeFileModel).filter_by(kb_name=kb_name, file_name=file_name).first()
    if file:
        file.qa_count = count

    session.commit()
    return True

@with_session
def update_file_to_db(session,
                kb_file: KnowledgeFile,
                docs_count: int = 0,
                custom_docs: bool = False,
                doc_infos: List[str] = [], # 形式：[{"id": str, "metadata": dict}, ...]
                ):
    kb = session.query(KnowledgeBaseModel).filter_by(kb_name=kb_file.kb_name).first()
    if kb:
        # 如果已经存在该文件，则更新文件信息
        existing_file: KnowledgeFileModel = (session.query(KnowledgeFileModel)
                                             .filter_by(file_name=kb_file.filename,
                                                        kb_name=kb_file.kb_name)
                                            .first())
        mtime = kb_file.get_mtime()
        size = kb_file.get_size()

        if existing_file:
            existing_file.file_mtime = mtime
            existing_file.file_size = size
            existing_file.docs_count = docs_count
            existing_file.custom_docs = custom_docs
        
        session.commit()
        update_docs_in_db(kb_name=kb_file.kb_name, file_name=kb_file.filename, doc_infos=doc_infos)
    return True

@with_session
def delete_file_from_db(session, kb_file: KnowledgeFile):
    existing_file = session.query(KnowledgeFileModel).filter_by(file_name=kb_file.filename,
                                                                kb_name=kb_file.kb_name).first()
    if existing_file:
        session.delete(existing_file)
        delete_docs_from_db(kb_name=kb_file.kb_name, file_name=kb_file.filename)
        session.commit()

        kb = session.query(KnowledgeBaseModel).filter_by(kb_name=kb_file.kb_name).first()
        if kb:
            kb.file_count -= 1

            sql_update = '''
            UPDATE course 
            SET file_name = NULL 
            WHERE kb_id = :kb_id AND file_name = :file_name
            '''
            session.execute(text(sql_update), {
                'kb_id': kb.id,
                'file_name': kb_file.filename
            })

            session.commit()
    return True


@with_session
def delete_files_from_db(session, knowledge_base_name: str):
    #删除所有该文件所有文件
    session.query(KnowledgeFileModel).filter_by(kb_name=knowledge_base_name).delete()
    #删除该知识库所有block
    session.query(FileDocModel).filter_by(kb_name=knowledge_base_name).delete()
    #删除知识库
    kb = session.query(KnowledgeBaseModel).filter_by(kb_name=knowledge_base_name).first()
    if kb:
        kb.file_count = 0

    session.commit()
    return True


@with_session
def file_exists_in_db(session, kb_file: KnowledgeFile):
    existing_file = session.query(KnowledgeFileModel).filter_by(file_name=kb_file.filename,
                                                                kb_name=kb_file.kb_name).first()
    return True if existing_file else False

import json

@with_session
def configs_update_to_db(session, kb_name: str,file_name: str,file_parse_configs: Dict):
    existing_file = session.query(KnowledgeFileModel).filter_by(kb_name=kb_name,file_name=file_name).first()

    if existing_file is None:
        return {"code":-1,"msg":"文件不存在","data":{}}
    
    # file_parse_configs = json.loads(file_parse_configs)
    # print(file_parse_configs)
    # for file_parse_config in file_parse_configs:
    #     for key in list(file_parse_config.keys()):
    #         if file_parse_config[key] is None:
    #             del file_parse_config[key]
    file_parse_configs = {key: value for key, value in file_parse_configs.items() if value is not None}
    print(file_parse_configs)
    if file_parse_configs:
        existing_file.file_parse_configs = file_parse_configs

    session.commit()
    return {"code":0,"msg":"成功","data":file_parse_configs}


@with_session
def get_file_detail(session, kb_name: str, file_name: str) -> dict:
    file: KnowledgeFileModel = (session.query(KnowledgeFileModel)
                                .filter_by(file_name=file_name,
                                            kb_name=kb_name).first())
    if file:
        return {
            "kb_name": file.kb_name,
            "file_name": file.file_name,
            "file_ext": file.file_ext,
            "file_version": file.file_version,
            "document_loader": file.document_loader_name,
            "text_splitter": file.text_splitter_name,
            "create_time": file.create_time,
            "file_mtime": file.file_mtime,
            "file_size": file.file_size,
            "custom_docs": file.custom_docs,
            "docs_count": file.docs_count,
            "qa_status":file.qa_status,
            "qa_count":file.qa_count,
            "parse_status":file.parse_status,
            "file_parse_configs":file.file_parse_configs
        }
    else:
        return {}


import math

def parse_content(response_json, token_limit, relative_path):
    # 添加空值检查
    full_text = response_json.get("text", "")
    data_list = response_json.get("data", [])

    if full_text is None:
        full_text = ""
    if data_list is None:
        data_list = []
    
    if not data_list:
        return [{"page_content": full_text, "meta_data": {"source": relative_path, "start": 0, "end": 0}}]
    
    if len(full_text) <= token_limit:
        return [{"page_content": full_text, "meta_data": {"source": relative_path, "start": data_list[0]["start"], "end": data_list[-1]["end"]}}]

    num_blocks = math.ceil(len(full_text) / token_limit)

    avg_count = len(data_list) // num_blocks
    remainder = len(data_list) % num_blocks

    chunks = []
    start_idx = 0
    for i in range(num_blocks):
        chunk_size = avg_count + (1 if i < remainder else 0)
        end_idx = start_idx + chunk_size

        chunk_data = data_list[start_idx:end_idx]
        chunk_text = "".join(item.get("text", "") for item in chunk_data)

        # 添加空值检查
        if chunk_data:
            chunk_start = chunk_data[0].get("start", 0)
            chunk_end = chunk_data[-1].get("end", 0)
        else:
            chunk_start = 0
            chunk_end = 0

        chunks.append({"page_content": chunk_text, "meta_data": {"source": relative_path, "start": chunk_start, "end": chunk_end}})
        start_idx = end_idx

    return chunks


#from chat_doc.configs.model_config import EMBEDDING_MODEL
from configs.model_config import EMBEDDING_MODEL
from server.db.models.knowledge_base_model import KnowledgeBaseModel
from server.db.models.course import Course
from server.db.session import with_session
from typing import List, Dict

@with_session
def kb_add(session,kb_name,kb_type,kb_info,create_user_email,dep_id,embedding_name):
    # 创建知识库实例
    kb = session.query(KnowledgeBaseModel).filter_by(kb_name=kb_name).first()
    if not kb:
        kb = KnowledgeBaseModel(kb_name=kb_name,kb_type=kb_type,kb_info=kb_info,create_user_email=create_user_email,dep_id=dep_id,activate="正常",embedding_name=embedding_name)
        session.add(kb)
        session.commit()
    else:  # update kb with new vs_type and embed_model
        old_dep_id = kb.dep_id
        if kb_name:
            kb.kb_name = kb_name
        if dep_id:
            kb.dep_id = dep_id

            if old_dep_id != dep_id:
                courses = session.query(Course).filter_by(kb_id=kb.id).all()
                for course in courses:
                    course.kb_id = None
                    course.file_name = None
                    course.exam_test_case = {}
                    course.exam_paper_status = '未生成'
                session.commit()

        if kb_info:
            kb.kb_info = kb_info
        if embedding_name:
            kb.embedding_name = embedding_name
        session.commit()
    kb = session.query(KnowledgeBaseModel).filter_by(kb_name=kb_name).first()
    return {"code":0,"msg":"","data":kb.to_out_dict()}

@with_session
def kb_update(session,kb_name,activate=None,embedding_name=None):

    kb = session.query(KnowledgeBaseModel).filter_by(kb_name=kb_name).first()
    if activate:
        kb.activate = activate
    if embedding_name:
        kb.embedding_name = embedding_name
        
    session.commit()
    return True

@with_session
def kb_list(session, dep_id: int = None, kb_name:str = None, kb_type: str = None, create_user_email:str = None, min_file_count: int = -1, page_start=None, page_end=None):
    kbs = session.query(KnowledgeBaseModel)

    kbs = kbs.filter_by(kb_type=kb_type)
    if dep_id:
        kbs = kbs.filter_by(dep_id=dep_id)
    if kb_name:
        kbs = kbs.filter(KnowledgeBaseModel.kb_name.like('%' + kb_name + '%'))
    if create_user_email:
        kbs = kbs.filter_by(create_user_email=create_user_email)

    kbs = kbs.filter(KnowledgeBaseModel.file_count > min_file_count)
    kbs = kbs.order_by(KnowledgeBaseModel.create_time.desc())
    kbs = kbs.order_by(KnowledgeBaseModel.id.desc())

    count=len(kbs.all())

    if page_start is not None and page_end is not None:
        kbs = kbs.slice(page_start, page_end).all()
    else:
        kbs = kbs.all()

    data = [kb.to_out_dict() for kb in kbs]
    return {"code":0,"msg":"成功","data":{"count":count,"kbs":data}}


@with_session
def kb_detail(session,id=None, kb_name=None,is_detail=True):
    
    kb = session.query(KnowledgeBaseModel)
    if kb is None:
        return {"code":-1,"msg":"错误","data":{}}
    if id:
        kb = kb.filter_by(id=id)
    if kb_name:
        kb = kb.filter_by(kb_name=kb_name)
    kb = kb.first()
    if kb is None:
        return {"code":-1,"msg":"错误","data":{}}
    return {"code":0,"msg":"成功","data":kb.to_out_dict(is_detail)}


@with_session
def _kb_name_list(session,
                    ids:list,
                    ) -> Dict:
    db_obj = session.query(KnowledgeBaseModel.id,KnowledgeBaseModel.kb_name).filter(KnowledgeBaseModel.id.in_(ids)).all()
    if db_obj is None:
        return {"code":-1,"msg":"数据不存在","data":[]}
    data = []
    for row in db_obj:
        data.append({"id":row.id,"kb_name":row.kb_name})
    return {"code":0,"msg":"成功","data":data}
   


@with_session
def kb_exists(session, kb_name):
    kb = session.query(KnowledgeBaseModel).filter_by(kb_name=kb_name).first()
    status = True if kb else False
    return status


@with_session
def load_kb_from_db(session, kb_name):
    kb = session.query(KnowledgeBaseModel).filter_by(kb_name=kb_name).first()
    if kb:
        kb_name, vs_type, embed_model = kb.kb_name,"faiss","bge-m3"
    else:
        kb_name, vs_type, embed_model = None, None, None
    return kb_name, vs_type, embed_model

@with_session
def load_kb_from_db_id(session, kb_id):
    kb = session.query(KnowledgeBaseModel).filter_by(id=kb_id).first()
    if kb:
        kb_name, vs_type, embed_model = kb.kb_name,"faiss","bge-m3"
    else:
        kb_name, vs_type, embed_model = None, None, None
    return kb_name, vs_type, embed_model


@with_session
def delete_kb_from_db(session, kb_name):
    kb = session.query(KnowledgeBaseModel).filter_by(kb_name=kb_name).first()
    if kb:
        kb_id = kb.id
        session.delete(kb)

        session.query(Course).filter_by(kb_id=kb_id).update({
            'kb_id': None,
            'file_name': None
        })
        
        session.commit()
    return True


@with_session
def get_kb_detail(session, kb_name: str) -> dict:
    kb: KnowledgeBaseModel = session.query(KnowledgeBaseModel).filter_by(kb_name=kb_name).first()
    if kb:
        return {
            "kb_name": kb.kb_name,
            "kb_info": kb.kb_info,
            "vs_type": "faiss",
            "embed_model": kb.embedding_name,
            "file_count": kb.file_count,
            "create_time": kb.create_time,
        }
    else:
        return {}

from datetime import datetime, timedelta, timezone
from pytz import timezone, UTC 

def beijing_time():
    """
    返回当前北京时间
    """
    utc_now = datetime.utcnow().replace(tzinfo=UTC)
    beijing_tz = timezone('Asia/Shanghai')
    beijing_now = utc_now.astimezone(beijing_tz)

    return beijing_now

@with_session
def check_temp_kb(session):

    current_time = beijing_time()
    
    # seven_days_ago = current_time - timedelta(days=7)
    seven_days_ago = current_time - timedelta(days=7)

    kbs_to_check = session.query(KnowledgeBaseModel).filter(
        KnowledgeBaseModel.kb_info == "临时知识库"
    ).all()

    # print("当前时间（北京时间）:", current_time)
    print("七天前的时间（北京时间）:", seven_days_ago)
    # print(kbs_to_check)

    expired_kb_names = []
    
    for kb in kbs_to_check:
        if kb.create_time:
            # print("记录的创建时间（原始）:", kb.create_time)
            kb_create_time_utc = kb.create_time
            kb_create_time_beijing = kb_create_time_utc.astimezone(timezone('Asia/Shanghai'))
            print("记录的创建时间（北京）:", kb.create_time)
            if kb_create_time_beijing < seven_days_ago:
                print("成功")
                expired_kb_names.append(kb.kb_name)
    
    return expired_kb_names

from server.db.models.knowledge_file_model import KnowledgeFileModel, FileDocModel
from server.db.models.test_case import TestCase

# @with_session
# def get_kb_export_data(session, kb_name):
#     """
#     获取知识库相关的所有数据库记录并生成SQL语句
#     """
#     # 获取knowledge_base表记录
#     kb_record = session.query(KnowledgeBaseModel).filter_by(kb_name=kb_name).first()
#     if not kb_record:
#         return None, "知识库不存在"
    
#     # 获取knowledge_file表记录
#     kf_records = session.query(KnowledgeFileModel).filter_by(kb_name=kb_name).all()
    
#     # 获取file_doc表记录
#     fd_records = session.query(FileDocModel).filter_by(kb_name=kb_name).all()
    
#     # 获取所有doc_id
#     doc_ids = [record.doc_id for record in fd_records]
    
#     # 获取test_case表中vs_id匹配的记录
#     tc_records = []
#     if doc_ids:
#         tc_records = session.query(TestCase).filter(TestCase.vs_id.in_(doc_ids)).all()
    
#     # 在同一个会话中生成SQL语句
#     sql_statements = []
    
#     # knowledge_base表的SQL
#     sql = (f"INSERT INTO knowledge_base (kb_name, kb_type, kb_info, file_count, create_time, "
#            f"create_user_email, dep_id, activate, embedding_name) "
#            f"VALUES ('{kb_record.kb_name}', '{kb_record.kb_type}', '{kb_record.kb_info}', "
#            f"{kb_record.file_count}, '{kb_record.create_time}', '{kb_record.create_user_email}', "
#            f"{kb_record.dep_id}, '{kb_record.activate}', '{kb_record.embedding_name}');")
#     sql_statements.append(sql)
    
#     # knowledge_file表的SQL
#     for record in kf_records:
#         file_parse_configs = str(record.file_parse_configs).replace("'", '"')
#         sql = (f"INSERT INTO knowledge_file (file_name, file_ext, kb_name, document_loader_name, "
#                f"text_splitter_name, file_version, file_mtime, file_size, custom_docs, docs_count, "
#                f"create_time, qa_status, qa_count, parse_status, file_parse_configs) "
#                f"VALUES ('{record.file_name}', '{record.file_ext}', '{record.kb_name}', "
#                f"'{record.document_loader_name}', '{record.text_splitter_name}', {record.file_version}, "
#                f"{record.file_mtime}, {record.file_size}, {record.custom_docs}, {record.docs_count}, "
#                f"'{record.create_time}', '{record.qa_status}', {record.qa_count}, "
#                f"'{record.parse_status}', '{file_parse_configs}');")
#         sql_statements.append(sql)
    
#     # file_doc表的SQL
#     for record in fd_records:
#         meta_data = str(record.meta_data).replace("'", '"')
#         page_content = record.page_content.replace("'", "''")
#         sql = (f"INSERT INTO file_doc (kb_name, file_name, doc_id, meta_data, page_content) "
#                f"VALUES ('{record.kb_name}', '{record.file_name}', '{record.doc_id}', "
#                f"'{meta_data}', '{page_content}');")
#         sql_statements.append(sql)
    
#     # test_case表的SQL
#     for record in tc_records:
#         question = record.question.replace("'", "''")
#         answer = record.answer.replace("'", "''")
#         sql = (f"INSERT INTO test_case (question, answer, vs_id, create_time, user_email, "
#                f"test_case_type, course_id, question_type) "
#                f"VALUES ('{question}', '{answer}', '{record.vs_id}', '{record.create_time}', "
#                f"'{record.user_email}', '{record.test_case_type}', {record.course_id}, "
#                f"'{record.question_type}');")
#         sql_statements.append(sql)
    
#     sql_content = '\n\n'.join(sql_statements)
    
#     return sql_content, None

@with_session
def get_kb_export_data(session, kb_name):
    """
    获取知识库相关的所有数据库记录并生成SQL语句
    """
    import json
    import re
    
    def escape_sql_string(value):
        """正确转义SQL字符串"""
        if value is None:
            return 'NULL'
        # 转换为字符串
        str_value = str(value)
        # 转义单引号 - 这是最重要的
        str_value = str_value.replace("'", "''")
        # 转义反斜杠
        str_value = str_value.replace("\\", "\\\\")
        # 转义百分号（防止SQLAlchemy误认为是绑定参数）
        str_value = str_value.replace("%", "%%")
        # 转义控制字符
        str_value = str_value.replace("\n", "\\n")
        str_value = str_value.replace("\r", "\\r")
        str_value = str_value.replace("\t", "\\t")
        # 移除NULL字符
        str_value = str_value.replace("\x00", "")
        str_value = str_value.replace("\x1a", "")
        # 确保所有字符串都用单引号包围
        return f"'{str_value}'"
    
    def escape_json_field(json_data):
        """正确处理JSON字段"""
        if json_data is None:
            return 'NULL'
        try:
            # 如果是字符串，尝试解析为JSON
            if isinstance(json_data, str):
                parsed_json = json.loads(json_data)
            else:
                parsed_json = json_data
            
            # 递归处理JSON中的数据，特别是格式化字符串和布尔值
            def clean_json_data(obj):
                if isinstance(obj, dict):
                    return {k: clean_json_data(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [clean_json_data(item) for item in obj]
                elif isinstance(obj, bool):
                    # 将布尔值转换为整数
                    return 1 if obj else 0
                elif isinstance(obj, str):
                    # 处理格式化字符串，替换为安全的占位符
                    cleaned = obj.replace("%(0)s", "__PLACEHOLDER_0__")
                    cleaned = cleaned.replace("%(1)s", "__PLACEHOLDER_1__")
                    cleaned = cleaned.replace("%(2)s", "__PLACEHOLDER_2__")
                    cleaned = cleaned.replace("%(3)s", "__PLACEHOLDER_3__")
                    cleaned = cleaned.replace("%(4)s", "__PLACEHOLDER_4__")
                    return cleaned
                else:
                    return obj
            
            cleaned_data = clean_json_data(parsed_json)
            
            # 重新序列化为标准JSON格式
            json_str = json.dumps(cleaned_data, ensure_ascii=False, separators=(',', ':'))
            # 转义单引号
            json_str = json_str.replace("'", "''")
            # 转义反斜杠
            json_str = json_str.replace("\\", "\\\\")
            # 转义百分号
            json_str = json_str.replace("%", "%%")
            return f"'{json_str}'"
        except (json.JSONDecodeError, TypeError) as e:
            # 如果JSON解析失败，记录错误并返回NULL
            print(f"JSON解析失败: {e}, 原始数据: {json_data}")
            return 'NULL'
    
    # 获取knowledge_base表记录
    kb_record = session.query(KnowledgeBaseModel).filter_by(kb_name=kb_name).first()
    if not kb_record:
        return None, "知识库不存在"
    
    # 获取knowledge_file表记录
    kf_records = session.query(KnowledgeFileModel).filter_by(kb_name=kb_name).all()
    
    # 获取file_doc表记录
    fd_records = session.query(FileDocModel).filter_by(kb_name=kb_name).all()
    
    # 获取所有doc_id
    doc_ids = [record.doc_id for record in fd_records]
    
    # 获取test_case表中vs_id匹配的记录
    tc_records = []
    if doc_ids:
        tc_records = session.query(TestCase).filter(TestCase.vs_id.in_(doc_ids)).all()
    
    # 在同一个会话中生成SQL语句
    sql_statements = []
    
    # knowledge_base表的SQL
    sql = (f"INSERT INTO knowledge_base (kb_name, kb_type, kb_info, file_count, create_time, "
           f"create_user_email, dep_id, activate, embedding_name) "
           f"VALUES ({escape_sql_string(kb_record.kb_name)}, {escape_sql_string(kb_record.kb_type)}, "
           f"{escape_sql_string(kb_record.kb_info)}, {kb_record.file_count}, "
           f"{escape_sql_string(kb_record.create_time)}, {escape_sql_string(kb_record.create_user_email)}, "
           f"{kb_record.dep_id}, {escape_sql_string(kb_record.activate)}, "
           f"{escape_sql_string(kb_record.embedding_name)});")
    sql_statements.append(sql)
    
    # knowledge_file表的SQL
    for record in kf_records:
        # 处理布尔值
        custom_docs_val = 'true' if record.custom_docs else 'false'
        
        sql = (f"INSERT INTO knowledge_file (file_name, file_ext, kb_name, document_loader_name, "
               f"text_splitter_name, file_version, file_mtime, file_size, custom_docs, docs_count, "
               f"create_time, qa_status, qa_count, parse_status, file_parse_configs) "
               f"VALUES ({escape_sql_string(record.file_name)}, {escape_sql_string(record.file_ext)}, "
               f"{escape_sql_string(record.kb_name)}, {escape_sql_string(record.document_loader_name)}, "
               f"{escape_sql_string(record.text_splitter_name)}, {record.file_version}, "
               f"{record.file_mtime}, {record.file_size}, {custom_docs_val}, {record.docs_count}, "
               f"{escape_sql_string(record.create_time)}, {escape_sql_string(record.qa_status)}, "
               f"{record.qa_count}, {escape_sql_string(record.parse_status)}, "
               f"{escape_json_field(record.file_parse_configs)});")
        sql_statements.append(sql)
    
    # file_doc表的SQL
    for record in fd_records:
        sql = (f"INSERT INTO file_doc (kb_name, file_name, doc_id, meta_data, page_content) "
               f"VALUES ({escape_sql_string(record.kb_name)}, {escape_sql_string(record.file_name)}, "
               f"{escape_sql_string(record.doc_id)}, {escape_json_field(record.meta_data)}, "
               f"{escape_sql_string(record.page_content)});")
        sql_statements.append(sql)
    
    # test_case表的SQL
    for record in tc_records:
        sql = (f"INSERT INTO test_case (question, answer, vs_id, create_time, user_email, "
               f"test_case_type, course_id, question_type) "
               f"VALUES ({escape_sql_string(record.question)}, {escape_sql_string(record.answer)}, "
               f"{escape_sql_string(record.vs_id)}, {escape_sql_string(record.create_time)}, "
               f"{escape_sql_string(record.user_email)}, {escape_sql_string(record.test_case_type)}, "
               f"{record.course_id}, {escape_sql_string(record.question_type)});")
        sql_statements.append(sql)
    
    sql_content = '\n\n'.join(sql_statements)
    
    return sql_content, None


# def execute_sql_import(sql_content: str):
#     """
#     执行SQL导入，直接执行SQL语句而不使用参数绑定
#     """
#     from server.db.base import engine
    
#     def split_sql_statements(sql_text):
#         """
#         智能分割SQL语句，避免在引号内的分号处分割
#         """
#         statements = []
#         current_statement = ""
#         in_single_quote = False
#         in_double_quote = False
#         i = 0
        
#         while i < len(sql_text):
#             char = sql_text[i]
            
#             if char == "'" and not in_double_quote:
#                 # 检查是否是转义的单引号
#                 if i > 0 and sql_text[i-1] == '\\':
#                     current_statement += char
#                 else:
#                     in_single_quote = not in_single_quote
#                     current_statement += char
#             elif char == '"' and not in_single_quote:
#                 # 检查是否是转义的双引号
#                 if i > 0 and sql_text[i-1] == '\\':
#                     current_statement += char
#                 else:
#                     in_double_quote = not in_double_quote
#                     current_statement += char
#             elif char == ';' and not in_single_quote and not in_double_quote:
#                 # 只有在不在引号内的分号才作为语句分隔符
#                 current_statement += char
#                 statements.append(current_statement.strip())
#                 current_statement = ""
#             else:
#                 current_statement += char
            
#             i += 1
        
#         # 添加最后一个语句（如果有的话）
#         if current_statement.strip():
#             statements.append(current_statement.strip())
        
#         return statements
    
#     try:
#         # 使用智能分割方法
#         statements = split_sql_statements(sql_content)
        
#         print(f"原始SQL内容前100字符: {repr(sql_content[:100])}")
#         print(f"分割后的语句数量: {len(statements)}")
#         for i, stmt in enumerate(statements):
#             print(f"语句 {i+1}: {repr(stmt[:50])}...")

#         # 过滤掉空语句和注释
#         statements = [stmt for stmt in statements if stmt and not stmt.strip().startswith('--')]
#         print(f"过滤后的语句数量: {len(statements)}")
#         print(f"检测到 {len(statements)} 条SQL语句")
        
#         # 获取原始连接
#         raw_conn = engine.raw_connection()
#         try:
#             cursor = raw_conn.cursor()
#             success_count = 0
#             error_count = 0
            
#             for i, statement in enumerate(statements, 1):
#                 try:
#                     print(f"执行第 {i} 条语句 (共 {len(statements)} 条)")
#                     print(f"语句预览: {statement[:100]}...")
                    
#                     # 直接执行原始SQL，不经过SQLAlchemy的参数处理
#                     cursor.execute(statement)
#                     raw_conn.commit()
#                     success_count += 1
#                     print(f"✓ 第 {i} 条语句执行成功")
                    
#                 except Exception as e:
#                     error_count += 1
#                     print(f"✗ 第 {i} 条语句执行失败: {str(e)}")
#                     print(f"失败的完整语句: {statement}")
#                     # 回滚当前事务，继续执行下一条
#                     try:
#                         raw_conn.rollback()
#                     except:
#                         pass
            
#             cursor.close()
#             print(f"\n导入完成: 成功 {success_count} 条，失败 {error_count} 条")
#             return error_count == 0
#         finally:
#             # 确保连接被正确关闭
#             raw_conn.close()
            
#     except Exception as e:
#         print(f"SQL导入过程中发生错误: {str(e)}")
#         return False


def execute_sql_import(sql_content: str, progress_callback=None):
    """
    执行SQL导入，支持流式进度回调
    """
    from server.db.base import engine
    
    def split_sql_statements(sql_text):
        """
        智能分割SQL语句，避免在引号内的分号处分割
        """
        statements = []
        current_statement = ""
        in_single_quote = False
        in_double_quote = False
        i = 0
        
        while i < len(sql_text):
            char = sql_text[i]
            
            if char == "'" and not in_double_quote:
                # 检查是否是转义的单引号
                if i > 0 and sql_text[i-1] == '\\':
                    current_statement += char
                else:
                    in_single_quote = not in_single_quote
                    current_statement += char
            elif char == '"' and not in_single_quote:
                # 检查是否是转义的双引号
                if i > 0 and sql_text[i-1] == '\\':
                    current_statement += char
                else:
                    in_double_quote = not in_double_quote
                    current_statement += char
            elif char == ';' and not in_single_quote and not in_double_quote:
                # 只有在不在引号内的分号才作为语句分隔符
                current_statement += char
                statements.append(current_statement.strip())
                current_statement = ""
            else:
                current_statement += char
            
            i += 1
        
        # 添加最后一个语句（如果有的话）
        if current_statement.strip():
            statements.append(current_statement.strip())
        
        return statements

    try:
        # 使用智能分割方法
        statements = split_sql_statements(sql_content)
        
        # 过滤掉空语句和注释
        statements = [stmt for stmt in statements if stmt and not stmt.strip().startswith('--')]
        total_statements = len(statements)
        
        if progress_callback:
            progress_callback({
                "type": "info",
                "message": f"检测到 {total_statements} 条SQL语句",
                "progress": 0
            })
        
        # 获取原始连接
        raw_conn = engine.raw_connection()
        try:
            cursor = raw_conn.cursor()
            success_count = 0
            error_count = 0
            
            for i, statement in enumerate(statements, 1):
                try:
                    # 计算进度百分比
                    progress_percent = int((i / total_statements) * 100)
                    
                    if progress_callback:
                        progress_callback({
                            "type": "progress",
                            "message": f"正在执行第 {i} 条语句 (共 {total_statements} 条)",
                            "progress": progress_percent
                        })
                    
                    # 直接执行原始SQL，不经过SQLAlchemy的参数处理
                    cursor.execute(statement)
                    raw_conn.commit()
                    success_count += 1
                    
                    if progress_callback:
                        progress_callback({
                            "type": "success",
                            "message": f"✓ 第 {i} 条语句执行成功",
                            "progress": progress_percent
                        })
                    
                except Exception as e:
                    error_count += 1
                    error_msg = f"✗ 第 {i} 条语句执行失败: {str(e)}"
                    
                    if progress_callback:
                        progress_callback({
                            "type": "error",
                            "message": error_msg,
                            "progress": int((i / total_statements) * 100)
                        })
                    
                    # 回滚当前事务，继续执行下一条
                    try:
                        raw_conn.rollback()
                    except:
                        pass
            
            cursor.close()
            
            # 最终完成状态
            if progress_callback:
                progress_callback({
                    "type": "complete",
                    "message": f"导入完成: 成功 {success_count} 条，失败 {error_count} 条",
                    "progress": 100
                })
            
            return error_count == 0
        finally:
            # 确保连接被正确关闭
            raw_conn.close()
            
    except Exception as e:
        error_msg = f"SQL导入过程中发生错误: {str(e)}"
        if progress_callback:
            progress_callback({
                "type": "fatal_error",
                "message": error_msg,
                "progress": 0
            })
        return False

@with_session
def update_kb_dep_id(session, kb_name: str, dep_id: int):
    """
    更新知识库的dep_id
    """
    kb = session.query(KnowledgeBaseModel).filter_by(kb_name=kb_name).first()
    if kb:
        kb.dep_id = dep_id
        session.commit()
        return True
    return False
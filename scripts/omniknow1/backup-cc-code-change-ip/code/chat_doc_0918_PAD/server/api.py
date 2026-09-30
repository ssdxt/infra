import nltk
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from configs import VERSION
from configs.model_config import NLTK_DATA_PATH
from configs.server_config import OPEN_CROSS_DOMAIN
import argparse
import uvicorn
from fastapi import Body
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import RedirectResponse
from server.chat.chat import chat
from server.chat.openai_chat import openai_chat
from server.chat.search_engine_chat import search_engine_chat
from server.chat.completion import completion
from server.chat.feedback import chat_feedback
from server.knowledge_base.kb_api import update_embedding,merge_kb,monitor_merge_kb

from server.embeddings_api import embed_texts_endpoint
from server.llm_api import (list_running_models, list_config_models,
                            change_llm_model, stop_llm_model,
                            get_model_config, list_search_engines)
from server.utils import (BaseResponse, ListResponse, FastAPI, MakeFastAPIOffline,
                          get_server_configs, get_prompt_template)
from typing import List, Literal

nltk.data.path = [NLTK_DATA_PATH] + nltk.data.path


async def document():
    return RedirectResponse(url="/docs")


def create_app(run_mode: str = None):
    app = FastAPI(
        title="Chat_Doc API Server",
        version=VERSION
    )
    
    MakeFastAPIOffline(app)
    # Add CORS middleware to allow all origins
    # 在config.py中设置OPEN_DOMAIN=True，允许跨域
    # set OPEN_DOMAIN=True in config.py to allow cross-domain
    if OPEN_CROSS_DOMAIN:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    mount_app_routes(app, run_mode=run_mode)
    return app


def mount_app_routes(app: FastAPI, run_mode: str = None):
    app.get("/",
            response_model=BaseResponse,
            summary="swagger 文档")(document)

    # Tag: Chat
#     app.post("/chat/fastchat",
#              tags=["Chat"],
#              summary="与llm模型对话(直接与fastchat api对话)",
#              )(openai_chat)

#     app.post("/chat/chat",
#              tags=["Chat"],
#              summary="与llm模型对话(通过LLMChain)",
#              )(chat)

#     app.post("/chat/search_engine_chat",
#              tags=["Chat"],
#              summary="与搜索引擎对话",
#              )(search_engine_chat)

#     app.post("/chat/feedback",
#              tags=["Chat"],
#              summary="返回llm模型对话评分",
#              )(chat_feedback)

    # 知识库相关接口
    mount_knowledge_routes(app)

    # LLM模型相关接口
#     app.post("/llm_model/list_running_models",
#              tags=["LLM Model Management"],
#              summary="列出当前已加载的模型",
#              )(list_running_models)

#     app.post("/llm_model/list_config_models",
#              tags=["LLM Model Management"],
#              summary="列出configs已配置的模型",
#              )(list_config_models)

#     app.post("/llm_model/get_model_config",
#              tags=["LLM Model Management"],
#              summary="获取模型配置（合并后）",
#              )(get_model_config)

#     app.post("/llm_model/stop",
#              tags=["LLM Model Management"],
#              summary="停止指定的LLM模型（Model Worker)",
#              )(stop_llm_model)

#     app.post("/llm_model/change",
#              tags=["LLM Model Management"],
#              summary="切换指定的LLM模型（Model Worker)",
#              )(change_llm_model)

#     # 服务器相关接口
#     app.post("/server/configs",
#              tags=["Server State"],
#              summary="获取服务器原始配置信息",
#              )(get_server_configs)

#     app.post("/server/list_search_engines",
#              tags=["Server State"],
#              summary="获取服务器支持的搜索引擎",
#              )(list_search_engines)

#     @app.post("/server/get_prompt_template",
#              tags=["Server State"],
#              summary="获取服务区配置的 prompt 模板")
#     def get_server_prompt_template(
#         type: Literal["llm_chat", "knowledge_base_chat", "search_engine_chat", "agent_chat"]=Body("llm_chat", description="模板类型，可选值：llm_chat，knowledge_base_chat，search_engine_chat，agent_chat"),
#         name: str = Body("default", description="模板名称"),
#     ) -> str:
#         return get_prompt_template(type=type, name=name)

#     # 其它接口
#     app.post("/other/completion",
#              tags=["Other"],
#              summary="要求llm模型补全(通过LLMChain)",
#              )(completion)

#     app.post("/other/embed_texts",
#             tags=["Other"],
#             summary="将文本向量化，支持本地模型和在线模型",
#             )(embed_texts_endpoint)



def mount_knowledge_routes(app: FastAPI):
    from server.chat.knowledge_base_chat import knowledge_base_chat,sentence_score_api
    from server.chat.agent_chat import agent_chat
    from server.knowledge_base.kb_api import list_kbs, create_kb, delete_kb,update_kb,detail_kb #,update_emb_model
    from server.knowledge_base.kb_doc_api import (list_files, list_files_self,detail_file,upload_docs, delete_docs,list_doc_block,update_doc_block,
                                                parse_docs,vectorize_docs,get_update_docs_configs,update_configs_to_db, download_doc, recreate_vector_store,delete_doc_block,
                                                search_docs, DocumentWithScore, update_info,download_img,download_file,upload_docs_by_path,clear_vs_by_source,
                                                update_doc_block_embedding,update_vectors_db,upload_docs_by_chat,create_temp_by_chat)
    
    from server.statistics.chat_history_api import feedback_chat_history_to_db_api
    from http_api.user_api import register_api,login_api,current_user_info,update_current_user,user_info,list_user,update_user,list_job,delete_user,update_user_app
#     from http_api.user_api import add_role,update_role,list_role,delete_role,detail_role
    
    
    from http_api.app_type_api import add_app_type,update_app_type,list_app_type,delete_app_type,detail_app_type
    from http_api.app_api import add_app,update_app,list_app,delete_app,detail_app,create_app_token,update_specific_app,list_specific_app,app_logo
    from server.http_api.chat_feedback_api import add_chat_feedback,update_chat_feedback,list_chat_feedback,delete_chat_feedback,detail_chat_feedback,check_chat_feedback
    from server.knowledge_base.export_kb import export_kb,import_kb

    #向量库相似度计算
    app.post("/other/sentence_score",
            tags=["Knowledge Base Management"],
            response_model=BaseResponse,
            summary="列出文档的所有docs")(sentence_score_api)

    app.post("/chat/knowledge_base_chat",
             tags=["Chat"],
             summary="与知识库对话")(knowledge_base_chat)
    

#     app.post("/chat/agent_chat",
#              tags=["Chat"],
#              summary="与agent对话")(agent_chat)
    

 # 助手对话反馈
    app.post("/chat/add_chat_feedback",
             tags=["Chat"],
             summary="新增反馈记录")(add_chat_feedback)
    
    app.post("/chat/update_chat_feedback",
             tags=["Chat"],
             summary="更新反馈记录")(update_chat_feedback)

    app.post("/chat/list_chat_feedback",
             tags=["Chat"],
             summary="查看反馈记录")(list_chat_feedback)

    app.post("/chat/delete_chat_feedback",
             tags=["Chat"],
             summary="删除反馈记录")(delete_chat_feedback)
    
    app.post("/chat/detail_chat_feedback",
             tags=["Chat"],
             summary="查看反馈记录详情")(detail_chat_feedback)

    app.post("/chat/check_chat_feedback",
             tags=["Chat"],
             summary="校验反馈记录")(check_chat_feedback)
    
    # 知识库
    app.post("/knowledge_base/list_kbs",
            tags=["Knowledge Base Management"],
            response_model=BaseResponse,
            summary="获取知识库列表")(list_kbs)

    app.post("/knowledge_base/create_kb",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="创建知识库"
             )(create_kb)
    
    app.post("/knowledge_base/update_kb",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="创建知识库"
             )(update_kb)

    app.post("/knowledge_base/delete_kb",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="删除知识库"
             )(delete_kb)
    app.post("/knowledge_base/detail_kb",
            tags=["Knowledge Base Management"],
            response_model=BaseResponse,
            summary="获取知识库列表")(detail_kb)
    
    app.post("/knowledge_base/export_kb",
            tags=["Knowledge Base Management"],
            response_model=BaseResponse,
            summary="导出知识库"
            )(export_kb)
            
    app.post("/knowledge_base/import_kb",
            tags=["Knowledge Base Management"],
            response_model=BaseResponse,
            summary="导出知识库"
            )(import_kb)

    #文件
    app.post("/knowledge_base/list_files",
            tags=["Knowledge Base Management"],
            response_model=BaseResponse,
            summary="获取知识库内的文件列表"
            )(list_files)
    
    app.post("/knowledge_base/detail_file",
            tags=["Knowledge Base Management"],
            response_model=BaseResponse,
            summary="获取文件信息"
            )(detail_file)
    
    #文件
    app.post("/knowledge_base/list_files_self",
            tags=["Knowledge Base Management"],
            response_model=BaseResponse,
            summary="获取知识库内的文件列表"
            )(list_files_self)
    
    app.post("/knowledge_base/upload_docs_by_path",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="上传文件到知识库(文件路径)"
             )(upload_docs_by_path)
    
    app.post("/knowledge_base/upload_docs",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="上传文件到知识库"
             )(upload_docs)
    
    app.post("/knowledge_base/upload_docs_by_chat",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="解析文件并存入知识库"
             )(upload_docs_by_chat)
    
    app.post("/knowledge_base/delete_docs",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="删除知识库内指定文件"
             )(delete_docs)
    
    app.post("/knowledge_base/update_embedding",
            tags=["Knowledge Base Management"],
            response_model=BaseResponse,
            summary="更新知识库编码"
            )(update_embedding)
    app.post("/knowledge_base/merge_kb",
            tags=["Knowledge Base Management"],
            response_model=BaseResponse,
            summary="合并两个向量库"
            )(merge_kb)
    app.post("/knowledge_base/monitor_merge_kb",
            tags=["Knowledge Base Management"],
            response_model=BaseResponse,
            summary="监控合并向量库"
            )(monitor_merge_kb)

    app.post("/knowledge_base/update_info",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="更新知识库介绍"
             )(update_info)
    
    app.post("/knowledge_base/parse_docs",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="解析文件并存入知识库"
             )(parse_docs)
    
#     app.post("/knowledge_base/vectorize_docs",
#              tags=["Knowledge Base Management"],
#              response_model=BaseResponse,
#              summary="文件向量化并更新到知识库"
#              )(vectorize_docs)
    
    app.post("/knowledge_base/clear_vs_by_source",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="删除source对应的向量库内容"
             )(clear_vs_by_source)
    
        #搜索知识库
    app.post("/knowledge_base/search_docs",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="搜索知识库"
             )(search_docs)
    
    app.post("/knowledge_base/get_update_docs_configs",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="获取上传文档的配置信息"
             )(get_update_docs_configs)

    app.post("/knowledge_base/update_configs_to_db",
             tags=["Knowledge Base Management"],
             response_model=BaseResponse,
             summary="上传文档的配置信息"
             )(update_configs_to_db)
    
    #列出文档的所有分块内容
    app.post("/knowledge_base/list_doc_block",
            tags=["Knowledge Base Management"],
            summary="列出文档的所有分块内容")(list_doc_block)
    
    #更新分块内容
    app.post("/knowledge_base/update_doc_block",
            tags=["Knowledge Base Management"],
            summary="更新分块内容")(update_doc_block)
    
    #删除分块内容
    app.post("/knowledge_base/delete_doc_block",
            tags=["Knowledge Base Management"],
            summary="删除分块内容")(delete_doc_block)
    
    #更新文档块向量库
    app.post("/knowledge_base/update_doc_block_embedding",
            tags=["Knowledge Base Management"],
            summary="更新文档块向量库")(update_doc_block_embedding)
    
    #更新文档向量库
    app.post("/knowledge_base/update_vectors_db",
            tags=["Knowledge Base Management"],
            summary="更新文档向量库")(update_vectors_db)
    
    #finetune向量模型
#     app.post("/knowledge_base/update_emb_model",
#              tags=["Knowledge Base Management"],
#              response_model=BaseResponse,
#              summary="更新emb模型"
#              )(update_emb_model)

    app.get("/knowledge_base/download_doc",
            tags=["Knowledge Base Management"],
            summary="下载对应的知识文件")(download_doc)
    #下载图片
    app.get("/knowledge_base/download_img",
            tags=["Knowledge Base Management"],
            summary="下载对应的图片")(download_img)

    #下载文件
    app.get("/knowledge_base/download_file",
            tags=["Knowledge Base Management"],
            summary="下载对应的图片")(download_file)

#     app.post("/knowledge_base/recreate_vector_store",
#              tags=["Knowledge Base Management"],
#              summary="根据content中文档重建向量库，流式输出处理进度。"
#              )(recreate_vector_store)


    #统计类
    #反馈聊天记录
    app.post("/statistics/feedback_chat_response",
            tags=["Knowledge Base Management"],
            summary="反馈聊天内容和分数")(feedback_chat_history_to_db_api)
    
    # app.post("/statistics/register_test",
    #         tags=["Knowledge Base Management"],
    #         summary="反馈聊天内容和分数")(register_test)

    from server.http_api.chat_history_api import chat_session_delete
    #对话临时数据库
    app.post("/chathistory/chat_session_delete",
            tags=["Knowledge Base Management"],
            summary="删除窗口及关联临时数据库")(chat_session_delete)
    
    app.post("/chathistory/create_temp_by_chat",
             tags=["Knowledge Base Management"],
             summary="文件上传（创建）临时数据库"
             )(create_temp_by_chat)
    
    #用户
    app.post("/user/register",
             tags=["user"],
             summary="注册")(register_api)
    app.post("/user/login",tags=["user"],
             summary="登录")(login_api)
    app.post("/user/update_current_user_info",tags=["user"],
                summary="修改用户信息")(update_current_user)
    app.post("/user/get_current_user_info",tags=["user"],
             summary="获取当前用户信息")(current_user_info)
    
    #admin权限
    app.post("/user/get_user_info",tags=["user"],
             summary="获取当前用户信息")(user_info)
    app.post("/user/update_user",tags=["user"],
                summary="修改用户权限")(update_user)
    app.post("/user/list_user",tags=["user"],
                summary="用户列表")(list_user)
    app.post("/user/delete_user",tags=["user"],
                summary="删除用户")(delete_user)
    
    #获取当前单位注册用户的所有岗位
    app.post("/user/list_job",tags=["user"],
                summary="用户列表")(list_job)
                
    app.post("/user/update_user_app",tags=["user"],
                summary="更新用户应用")(update_user_app)

    from http_api.doc_generation_api import add_doc_template,update_doc_template,delete_doc_template,detail_doc_template,list_doc_template
    from http_api.doc_generation_api import add_doc_history,list_doc_history,detail_doc_history,delete_doc_history
    #文档生成
    app.post("/doc_generate/add_doc_template",tags=["doc_generate"],
                summary="增加文档模板")(add_doc_template)
    app.post("/doc_generate/update_doc_template",tags=["doc_generate"],
                summary="更新文档模板")(update_doc_template)
    app.post("/doc_generate/list_doc_template",tags=["doc_generate"],
                summary="列出文档模板")(list_doc_template)
    app.post("/doc_generate/detail_doc_template",tags=["doc_generate"],
                summary="详细文档模板")(detail_doc_template)
    app.post("/doc_generate/delete_doc_template",tags=["doc_generate"],
                summary="删除文档模板")(delete_doc_template)
    #文档历史
    app.post("/doc_generate/add_doc_history",tags=["doc_generate"],
                summary="增加文档生成记录")(add_doc_history)
    app.post("/doc_generate/list_doc_history",tags=["doc_generate"],
                summary="列出文档生成记录")(list_doc_history)
    app.post("/doc_generate/detail_doc_history",tags=["doc_generate"],
                summary="查询文档生成记录")(detail_doc_history)
    app.post("/doc_generate/delete_doc_history",tags=["doc_generate"],
                summary="查询文档生成记录")(delete_doc_history)
    
    from http_api.tools_api import get_chat_default_config,generate_qa_pairs,generate_keywords,generate_abstract,generate_query_intent,generate_paragraph,generate_course_abstract,generate_course_directory,generate_exam_score,page_get_qa,logo_get,generate_course_exam_new, generate_exam_score_new,list_embedding_model,get_progress,generate_chapter_abstract,layout_file,parse_img_exam, parse_pdf_exam

    #工具类
    app.post("/tools/parse_img_exam",tags=["doc_generate"],
                summary="试题结构化图片")(parse_img_exam)
    app.post("/tools/parse_pdf_exam",tags=["doc_generate"],
                summary="试题结构化文档")(parse_pdf_exam)
    
    app.post("/tools/generate_qa_pairs",tags=["doc_generate"],
                summary="生成问答对")(generate_qa_pairs)
    app.post("/tools/generate_keywords",tags=["doc_generate"],
                summary="生成关键字")(generate_keywords)
    app.post("/tools/generate_abstract",tags=["doc_generate"],
                summary="生成摘要")(generate_abstract)
    app.post("/tools/generate_query_intent",tags=["doc_generate"],
                summary="生成意图")(generate_query_intent)
    
    app.post("/tools/generate_course_directory",tags=["doc_generate"],
                summary="生成课程目录")(generate_course_directory)

    app.post("/tools/generate_course_abstract",tags=["doc_generate"],
                summary="生成课程摘要")(generate_course_abstract)

    app.post("/tools/generate_exam_score",tags=["doc_generate"],
                summary="生成考题分数")(generate_exam_score)
    
    app.post("/tools/page_get_qa",tags=["doc_generate"],
                summary="页码获得问答对")(page_get_qa)
    
    app.post("/doc_generate/generate_paragraph",tags=["doc_generate"],
                summary="生成文档内容")(generate_paragraph)

    app.post("/tools/logo_get",tags=["doc_generate"],
                summary="logo上传")(logo_get) 
    
    app.post("/tools/generate_course_exam",tags=["doc_generate"],
                summary="生成考题")(generate_course_exam_new)
    
#     app.post("/tools/parse_pdf_exam",tags=["doc_generate"],
#                 summary="试题结构化文档")(parse_pdf_exam)

    app.post("/tools/list_embedding_model",tags=["doc_generate"],
                summary="获取向量模型")(list_embedding_model)
    
    app.post("/tools/get_progress",tags=["doc_generate"],
                summary="获取解析进度")(get_progress)
    
    app.post("/tools/generate_chapter_abstract",tags=["doc_generate"],
                summary="生成全文及章节摘要")(generate_chapter_abstract)
    
    app.post("/tools/layout_file",tags=["doc_generate"],
                summary="版面分析")(layout_file)
    
    app.post("/tools/get_chat_default_config",tags=["doc_generate"],
                summary="获取助手默认配置")(get_chat_default_config)
    
#     app.post("/tools/run_all_migrations",tags=["doc_generate"],
#                 summary="数据库迁移")(run_all_migrations)
    
    #app
    app.post("/app/add_app_type",tags=["app"],
                summary="")(add_app_type)
    app.post("/app/update_app_type",tags=["app"],
                summary="")(update_app_type)
    app.post("/app/list_app_type",tags=["app"],
                summary="")(list_app_type)
    app.post("/app/delete_app_type",tags=["app"],
                summary="")(delete_app_type)
    app.post("/app/detail_app_type",tags=["app"],
                summary="")(detail_app_type)
    
    app.post("/app/add_app",tags=["app"],
                summary="")(add_app)
    app.post("/app/update_app",tags=["app"],
                summary="")(update_app)
    app.post("/app/list_app",tags=["app"],
                summary="")(list_app)
    app.post("/app/delete_app",tags=["app"],
                summary="")(delete_app)
    app.post("/app/detail_app",tags=["app"],
                summary="")(detail_app)
    app.post("/app/create_app_token",tags=["app"],
                summary="")(create_app_token)
    app.post("/app/update_specific_app",tags=["app"],
                summary="")(update_specific_app)
    app.post("/app/list_specific_app",tags=["app"],
                summary="")(list_specific_app)
    app.post("/app/app_logo",tags=["app"],
                summary="")(app_logo)
    
    from server.http_api.department_api import add_department,update_department,list_department,delete_department,detail_department
    #部门
    app.post("/department/add_department",tags=["department"],
                summary="")(add_department)
    app.post("/department/update_department",tags=["department"],
                summary="")(update_department)
    app.post("/department/list_department",tags=["department"],
                summary="")(list_department)
    
    app.post("/department/delete_department",tags=["department"],
                summary="")(delete_department)
    
    app.post("/department/detail_department",tags=["department"],
                summary="")(detail_department)
    
    from server.http_api.course_api import add_course ,update_course,list_course,delete_course,detail_course
    from server.http_api.course_eval_api import add_course_eval,list_course_eval,update_course_eval,delete_course_eval,list_student_profile,calculate_score
    from server.http_api.test_case_api import add_test_case,update_test_case,list_test_case,delete_test_case,generate_test_paper,delete_test_case,detail_test_case,generate_test_cases,generate_test_cases_status,generate_exam_paper,list_exam_paper,update_exam_paper
    from server.http_api.test_history_api import add_test_history,update_test_history,list_test_history,delete_test_history,generate_suggestion_test_history,generate_reference_test_history,list_eval_test_case
    from server.http_api.test_record_api import update_test_record,list_test_record

    app.post("/train/add_course",tags=["train"],
                summary="增加课程")(add_course)
    app.post("/train/update_course",tags=["train"],
                summary="更新课程")(update_course)
    app.post("/train/list_course",tags=["train"],
                summary="列出课程")(list_course)
    app.post("/train/detail_course",tags=["train"],
                summary="课程详情")(detail_course)
    app.post("/train/delete_course",tags=["train"],
                summary="删除课程")(delete_course)

    app.post("/train/add_course_eval",tags=["train"],
                summary="创建考试记录")(add_course_eval)
    app.post("/train/update_course_eval",tags=["train"],
                summary="更新考试记录")(update_course_eval)
    app.post("/train/list_course_eval",tags=["train"],
                summary="列出考试记录")(list_course_eval)
    app.post("/train/delete_course_eval",tags=["train"],
                summary="删除考试记录")(delete_course_eval)
    app.post("/train/list_student_profile",tags=["train"],
                summary="查看学员记录")(list_student_profile)
    
    app.post("/train/add_test_case",tags=["train"],
                summary="创建试题")(add_test_case)
    app.post("/train/update_test_case",tags=["train"],
                summary="更新试题")(update_test_case)
    app.post("/train/list_test_case",tags=["train"],
                summary="列出试题")(list_test_case)
    app.post("/train/delete_test_case",tags=["train"],
                summary="删除试题")(delete_test_case)
    
    app.post("/train/generate_test_paper",tags=["train"],
                summary="生成试卷")(generate_test_paper)
    
    app.post("/train/generate_test_cases",tags=["train"],
                summary="题库生成")(generate_test_cases)
    app.post("/train/generate_test_cases_status",tags=["train"],
                summary="题库生成状态")(generate_test_cases_status)
    
    app.post("/train/generate_exam_paper",tags=["train"],
                summary="统一试卷生成")(generate_exam_paper)
    app.post("/train/list_exam_paper",tags=["train"],
                summary="列出统一试卷")(list_exam_paper)
    app.post("/train/update_exam_paper",tags=["train"],
                summary="列出统一试卷")(update_exam_paper)

    app.post("/train/add_test_history",tags=["train"],
                summary="增加做题记录")(add_test_history)
    app.post("/train/list_test_history",tags=["train"],
                summary="列出做题记录")(list_test_history)
    app.post("/train/update_test_history",tags=["train"],
                summary="更新做题记录")(update_test_history)
    app.post("/train/delete_test_history",tags=["train"],
                summary="删除做题记录")(delete_test_history)
    
    app.post("/train/calculate_score",tags=["train"],
                summary="试卷总分计算")(calculate_score)
    
    app.post("/train/list_eval_test_case",tags=["train"],
                summary="查看考试情况")(list_eval_test_case)

    app.post("/train/update_test_record",tags=["train"],
                summary="更新培训建议记录")(update_test_record)
    app.post("/train/list_test_record",tags=["train"],
                summary="列出培训建议记录")(list_test_record)
    
    app.post("/train/generate_suggestion_test_history",tags=["train"],
                summary="生成培训建议")(generate_suggestion_test_history)
    app.post("/train/generate_reference_test_history",tags=["train"],
                summary="生成参考资料建议")(generate_reference_test_history)
    
    from server.http_api.statistics_api import all_statistic,user_statistic,course_statistic,app_statistic,knowledge_statistic,doc_statistic,test_case_statistic,job_title_statistic

    app.post("/statictics/all_statistic",tags=["statictics"],
                summary="所有")(all_statistic)
    app.post("/statictics/user_statistic",tags=["statictics"],
                summary="用户")(user_statistic)
    app.post("/statictics/course_statistic",tags=["statictics"],
                summary="课程")(course_statistic)
    app.post("/statictics/app_statistic",tags=["statictics"],
                summary="应用")(app_statistic)
    app.post("/statictics/knowledge_statistic",tags=["statictics"],
                summary="知识库")(knowledge_statistic)
    app.post("/statictics/doc_statistic",tags=["statictics"],
                summary="文档")(doc_statistic)
    app.post("/statictics/test_case_statistic",tags=["statictics"],
                summary="题库")(test_case_statistic)
    app.post("/statictics/job_title_statistic",tags=["statictics"],
                summary="题库")(job_title_statistic)
    


def run_api(host, port, **kwargs):
    if kwargs.get("ssl_keyfile") and kwargs.get("ssl_certfile"):
        uvicorn.run(app,
                    host=host,
                    port=port,
                    ssl_keyfile=kwargs.get("ssl_keyfile"),
                    ssl_certfile=kwargs.get("ssl_certfile"),
                    workers=16
                    )
    else:
        uvicorn.run(app, host=host, port=port,workers=16)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog='',
                                     description='')
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=7861)
    parser.add_argument("--ssl_keyfile", type=str)
    parser.add_argument("--ssl_certfile", type=str)
    # 初始化消息
    args = parser.parse_args()
    args_dict = vars(args)

    app = create_app()
    mount_knowledge_routes(app)

    run_api(host=args.host,
            port=args.port,
            ssl_keyfile=args.ssl_keyfile,
            ssl_certfile=args.ssl_certfile,
            
            )

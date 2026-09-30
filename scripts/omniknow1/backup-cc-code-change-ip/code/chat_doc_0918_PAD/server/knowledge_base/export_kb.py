import os
import tempfile
import shutil
from datetime import datetime
from server.db.repository.knowledge_base_repository import get_kb_export_data,delete_kb_from_db,execute_sql_import,update_kb_dep_id
from server.db.repository.knowledge_file_repository import delete_tc_by_kbfile,delete_files_from_db
from sqlalchemy import text
import py7zr
from server.utils import BaseResponse
from fastapi import Depends,UploadFile,File,Form
from server.http_api.user_api import admin_token_check
from urllib.parse import urlencode
from pydantic import BaseModel


class ExportKbParams(BaseModel):
    kb_name: str
    password: str

def export_kb(params: ExportKbParams, user_dict=Depends(admin_token_check)):
    """
    导出知识库为加密7z包
    """
    try:
        # 检查知识库文件夹是否存在
        kb_folder_path = os.path.join("knowledge_base", params.kb_name)
        if not os.path.exists(kb_folder_path):
            return BaseResponse(code=400, msg=f"知识库文件夹 {params.kb_name} 不存在")
        
        # 获取SQL内容
        sql_content, error = get_kb_export_data(params.kb_name)
        if error:
            return BaseResponse(code=400, msg=error)
        
        # 创建临时目录
        with tempfile.TemporaryDirectory() as temp_dir:
            # 复制知识库文件夹到临时目录
            temp_kb_folder = os.path.join(temp_dir, params.kb_name)
            shutil.copytree(kb_folder_path, temp_kb_folder)
            
            # 创建SQL文件到临时知识库文件夹中
            sql_file_path = os.path.join(temp_kb_folder, "database_records.sql")
            with open(sql_file_path, 'w', encoding='utf-8') as f:
                # f.write(f"-- 知识库 {params.kb_name} 数据库记录导出\n")
                # f.write(f"-- 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(sql_content)
            
            # 创建加密7z文件，存放在knowledge_base目录下对应的知识库路径中
            zip_filename = f"{params.kb_name}.7z"
            zip_file_path = os.path.join(kb_folder_path, zip_filename)
            
            # 确保目录存在
            os.makedirs(os.path.dirname(zip_file_path), exist_ok=True)
            
            # 使用py7zr直接创建加密的7z文件
            with py7zr.SevenZipFile(zip_file_path, 'w', password=params.password) as archive:
                # 添加知识库文件夹中的所有文件，保持相对路径
                for root, dirs, files in os.walk(temp_kb_folder):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # 计算相对于temp_dir的路径，保持知识库文件夹名称
                        arcname = os.path.relpath(file_path, temp_dir)
                        # 标准化路径分隔符为正斜杠
                        arcname = arcname.replace(os.path.sep, '/')
                        archive.write(file_path, arcname)
            
            file_location_relative = os.path.join("knowledge_base", params.kb_name, zip_filename)
            
            # 构建URL参数
            _file_url_request_parameters = urlencode({
                "filepath": file_location_relative, 
                "filename": zip_filename
            })
            _file_url = f"knowledge_base/download_file?" + _file_url_request_parameters
            
            return BaseResponse(
                code=200, 
                msg="知识库导出成功", 
                data={
                    "download_url": _file_url,
                    "export_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                }
            )
            
    except Exception as e:
        return BaseResponse(code=500, msg=f"导出失败: {str(e)}")


# def import_kb(
#     file: UploadFile = File(..., description="加密的知识库文件"),
#     password: str = Form(..., description="知识库密码"),
#     user_dict=Depends(admin_token_check)
# ) -> BaseResponse:
#     """
#     导入知识库从加密包
#     """
#     user =user_dict["user"]
#     user_email=user["email"]
#     dep_id = user["dep_id"]

#     try:
#         if not file.filename.endswith('.7z'):
#             return BaseResponse(code=400, msg="只支持.7z格式的文件")
        
#         with tempfile.TemporaryDirectory() as temp_dir:
#             temp_file_path = os.path.join(temp_dir, file.filename)
#             with open(temp_file_path, 'wb') as f:
#                 content = file.file.read()
#                 f.write(content)
            
#             extract_dir = os.path.join(temp_dir, "extracted")
#             os.makedirs(extract_dir, exist_ok=True)
            
#             try:
#                 with py7zr.SevenZipFile(temp_file_path, mode='r', password=password) as archive:
#                     archive.extractall(path=extract_dir)
#             except Exception as e:
#                 return BaseResponse(code=400, msg=f"解压失败，请检查密码是否正确: {str(e)}")
            
#             # 查找解压出的知识库文件夹
#             extracted_items = os.listdir(extract_dir)
#             if not extracted_items:
#                 return BaseResponse(code=400, msg="解压后未找到任何文件")
            
#             # 假设第一个文件夹就是知识库文件夹
#             kb_folder_name = None
#             for item in extracted_items:
#                 item_path = os.path.join(extract_dir, item)
#                 if os.path.isdir(item_path):
#                     kb_folder_name = item
#                     break
            
#             if not kb_folder_name:
#                 return BaseResponse(code=400, msg="解压后未找到知识库文件夹")
            
#             extracted_kb_path = os.path.join(extract_dir, kb_folder_name)
            
#             # 检查SQL文件是否存在
#             sql_file_path = os.path.join(extracted_kb_path, "database_records.sql")
#             if not os.path.exists(sql_file_path):
#                 return BaseResponse(code=400, msg="未找到数据库记录文件 database_records.sql")
            
#             # 检查knowledge_base目录下是否存在同名知识库
#             target_kb_path = os.path.join("knowledge_base", kb_folder_name)
            
#             # 如果存在同名知识库，删除文件夹和数据库记录
#             if os.path.exists(target_kb_path):
#                 try:
#                     # 删除数据库中的相关记录
#                     delete_tc_by_kbfile(kb_folder_name)
#                     delete_files_from_db(kb_folder_name)
#                     delete_kb_from_db(kb_folder_name)
                    
#                     # 删除文件夹
#                     shutil.rmtree(target_kb_path)
#                 except Exception as e:
#                     return BaseResponse(code=500, msg=f"删除同名知识库失败: {str(e)}")
            
#             # 复制解压的知识库文件夹到knowledge_base目录
#             try:
#                 shutil.copytree(extracted_kb_path, target_kb_path)
#             except Exception as e:
#                 return BaseResponse(code=500, msg=f"复制知识库文件夹失败: {str(e)}")
            
#             # 读取并执行SQL文件
#             try:
#                 with open(sql_file_path, 'r', encoding='utf-8') as f:
#                     sql_content = f.read()
                
#                 # 执行SQL语句导入数据
#                 execute_sql_import(sql_content)
#                 update_kb_dep_id(kb_folder_name, dep_id)

#             except Exception as e:
#                 # SQL执行失败，删除已复制的文件夹
#                 if os.path.exists(target_kb_path):
#                     shutil.rmtree(target_kb_path)
#                 return BaseResponse(code=500, msg=f"导入数据库记录失败: {str(e)}")
            
#             return BaseResponse(
#                 code=200,
#                 msg="知识库导入成功",
#                 data={
#                     "kb_name": kb_folder_name,
#                     "import_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
#                 }
#             )
            
#     except Exception as e:
#         return BaseResponse(code=500, msg=f"导入失败: {str(e)}")


from fastapi.responses import StreamingResponse
import json
import asyncio
from typing import Generator

def import_kb(
    file: UploadFile = File(..., description="加密的知识库文件"),
    password: str = Form(..., description="知识库密码"),
    user_dict=Depends(admin_token_check)
) -> StreamingResponse:
    """
    导入知识库，实时返回进度
    """
    def generate_progress() -> Generator[str, None, None]:
        user = user_dict["user"]
        user_email = user["email"]
        dep_id = user["dep_id"]
        
        try:
            if not file.filename.endswith('.7z'):
                yield f"{json.dumps({'type': 'error', 'message': '只支持.7z格式的文件'}, ensure_ascii=False)}\n\n"
                return
            
            yield f"{json.dumps({'type': 'info', 'message': '开始解压文件...', 'progress': 0}, ensure_ascii=False)}\n\n"
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_file_path = os.path.join(temp_dir, file.filename)
                with open(temp_file_path, 'wb') as f:
                    content = file.file.read()
                    f.write(content)
                
                extract_dir = os.path.join(temp_dir, "extracted")
                os.makedirs(extract_dir, exist_ok=True)
                
                try:
                    with py7zr.SevenZipFile(temp_file_path, mode='r', password=password) as archive:
                        archive.extractall(path=extract_dir)
                    yield f"{json.dumps({'type': 'info', 'message': '文件解压成功', 'progress': 10}, ensure_ascii=False)}\n\n"
                except Exception as e:
                    yield f"{json.dumps({'type': 'error', 'message': f'解压失败，请检查密码是否正确'}, ensure_ascii=False)}\n\n"
                    return
                
                extracted_items = os.listdir(extract_dir)
                if not extracted_items:
                    yield f"{json.dumps({'type': 'error', 'message': '解压后未找到任何文件'}, ensure_ascii=False)}\n\n"
                    return
                
                kb_folder_name = None
                for item in extracted_items:
                    item_path = os.path.join(extract_dir, item)
                    if os.path.isdir(item_path):
                        kb_folder_name = item
                        break
                
                if not kb_folder_name:
                    yield f"{json.dumps({'type': 'error', 'message': '解压后未找到知识库文件夹'}, ensure_ascii=False)}\n\n"
                    return
                
                extracted_kb_path = os.path.join(extract_dir, kb_folder_name)
                
                # 检查SQL文件是否存在
                sql_file_path = os.path.join(extracted_kb_path, "database_records.sql")
                if not os.path.exists(sql_file_path):
                    yield f"{json.dumps({'type': 'error', 'message': '未找到数据库记录文件 database_records.sql'}, ensure_ascii=False)}\n\n"
                    return
                
                yield f"{json.dumps({'type': 'info', 'message': f'找到知识库: {kb_folder_name}', 'progress': 20}, ensure_ascii=False)}\n\n"
                
                # 检查knowledge_base目录下是否存在同名知识库
                target_kb_path = os.path.join("knowledge_base", kb_folder_name)
                
                # 如果存在同名知识库，删除文件夹和数据库记录
                if os.path.exists(target_kb_path):
                    try:
                        yield f"{json.dumps({'type': 'info', 'message': '删除同名知识库...', 'progress': 25}, ensure_ascii=False)}\n\n"
                        # 删除数据库中的相关记录
                        delete_tc_by_kbfile(kb_folder_name)
                        delete_files_from_db(kb_folder_name)
                        delete_kb_from_db(kb_folder_name)
                        
                        # 删除文件夹
                        shutil.rmtree(target_kb_path)
                        yield f"{json.dumps({'type': 'info', 'message': '同名知识库删除成功', 'progress': 30}, ensure_ascii=False)}\n\n"
                    except Exception as e:
                        yield f"{json.dumps({'type': 'error', 'message': f'删除同名知识库失败: {str(e)}'}, ensure_ascii=False)}\n\n"
                        return
                
                try:
                    yield f"{json.dumps({'type': 'info', 'message': '复制知识库文件...', 'progress': 35}, ensure_ascii=False)}\n\n"
                    shutil.copytree(extracted_kb_path, target_kb_path)
                    yield f"{json.dumps({'type': 'info', 'message': '知识库文件复制成功', 'progress': 40}, ensure_ascii=False)}\n\n"
                except Exception as e:
                    yield f"{json.dumps({'type': 'error', 'message': f'复制知识库文件夹失败: {str(e)}'}, ensure_ascii=False)}\n\n"
                    return
                
                try:
                    with open(sql_file_path, 'r', encoding='utf-8') as f:
                        sql_content = f.read()
                    
                    yield f"{json.dumps({'type': 'info', 'message': '开始导入数据库记录...', 'progress': 45}, ensure_ascii=False)}\n\n"
                    
                    # 进度回调函数
                    def progress_callback(progress_data):
                        # 将SQL执行进度映射到总进度的45%-95%区间
                        sql_progress = progress_data.get('progress', 0)
                        total_progress = 45 + int(sql_progress * 0.5)  # 45% + (0-50%)
                        
                        progress_data['progress'] = total_progress
                        return f"{json.dumps(progress_data, ensure_ascii=False)}\n\n"
                    
                    # 执行SQL语句导入数据，使用流式进度回调
                    def sql_progress_generator():
                        def callback(data):
                            nonlocal progress_callback
                            yield progress_callback(data)
                        
                        execute_sql_import_stream(sql_content, callback)
                    
                    progress_messages = []
                    
                    def collect_progress(data):
                        progress_messages.append(progress_callback(data))
                    
                    # 执行SQL导入
                    success = execute_sql_import(sql_content, collect_progress)
                    
                    # 输出收集到的进度消息
                    for msg in progress_messages:
                        yield msg
                    
                    if success:
                        update_kb_dep_id(kb_folder_name, dep_id)
                        yield f"{json.dumps({'type': 'complete', 'message': '知识库导入成功', 'progress': 100}, ensure_ascii=False)}\n\n"
                    else:
                        # SQL执行失败，删除已复制的文件夹
                        if os.path.exists(target_kb_path):
                            shutil.rmtree(target_kb_path)
                        yield f"{json.dumps({'type': 'error', 'message': '数据库导入失败，已回滚文件操作'}, ensure_ascii=False)}\n\n"
                        return
                        
                except Exception as e:
                    # SQL执行失败，删除已复制的文件夹
                    if os.path.exists(target_kb_path):
                        shutil.rmtree(target_kb_path)
                    yield f"{json.dumps({'type': 'error', 'message': f'导入数据库记录失败: {str(e)}'}, ensure_ascii=False)}\n\n"
                    return
                
        except Exception as e:
            yield f"{json.dumps({'type': 'error', 'message': f'导入失败: {str(e)}'}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(
        generate_progress(),
        media_type="text/plain",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Content-Type": "text/event-stream"
        }
    )
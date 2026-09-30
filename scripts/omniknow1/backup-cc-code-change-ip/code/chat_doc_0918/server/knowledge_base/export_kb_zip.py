import os
import zipfile
import tempfile
import shutil
from datetime import datetime
from server.db.repository.knowledge_base_repository import get_kb_export_data
from sqlalchemy import text
import pyminizip
from server.utils import BaseResponse
from fastapi import Depends
from server.http_api.user_api import admin_token_check
from urllib.parse import urlencode
from pydantic import BaseModel


class ExportKbParams(BaseModel):
    kb_name: str
    password: str

def export_kb(params: ExportKbParams, user_dict=Depends(admin_token_check)):
    """
    导出知识库为加密zip包
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
                f.write(f"-- 知识库 {params.kb_name} 数据库记录导出\n")
                f.write(f"-- 导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                f.write(sql_content)
            
            # 创建加密zip文件，存放在knowledge_base目录下对应的知识库路径中
            zip_filename = f"{params.kb_name}.zip"
            zip_file_path = os.path.join(kb_folder_path, zip_filename)
            
            # 确保目录存在
            os.makedirs(os.path.dirname(zip_file_path), exist_ok=True)
            
            # 使用标准zipfile创建压缩包，然后用pyminizip加密
            temp_zip_path = os.path.join(tempfile.gettempdir(), f"{params.kb_name}.zip")
            
            with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                # 添加知识库文件夹中的所有文件，保持相对路径
                for root, dirs, files in os.walk(temp_kb_folder):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # 计算相对于temp_dir的路径，保持知识库文件夹名称
                        arcname = os.path.relpath(file_path, temp_dir)

                        zipf.write(file_path, arcname)
            
            # 使用pyminizip重新创建加密版本
            files_to_compress = [temp_zip_path]
            prefixes = [""]
            
            # 创建最终的加密zip文件
            pyminizip.compress_multiple(files_to_compress, prefixes, zip_file_path, params.password, 5)
            
            # 清理临时文件
            os.remove(temp_zip_path)
            os.remove(sql_file_path)  # 删除临时SQL文件，因为已经包含在zip中
            
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
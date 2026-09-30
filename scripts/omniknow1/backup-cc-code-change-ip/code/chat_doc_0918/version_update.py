from typing import List, Dict
from server.db.session import with_session
from sqlalchemy import inspect,text
import json
from server.knowledge_base.kb_service.base import KBServiceFactory

@with_session
def migrate_eval_history(session) -> Dict:
    """
    数据库迁移函数：为 eval_history 表新增 eval_type 字段并更新所有记录为 "培训考核"
    """
    check_column_sql = """
    PRAGMA table_info(eval_history)
    """
    columns = session.execute(text(check_column_sql)).fetchall()
    column_names = [column[1] for column in columns]

    if 'eval_type' not in column_names:
        alter_table_sql = """
        ALTER TABLE eval_history ADD COLUMN eval_type VARCHAR(10)
        """
        session.execute(text(alter_table_sql))
        session.commit()

    update_eval_type_sql = """
    UPDATE eval_history SET eval_type = '培训考核'
    """
    session.execute(text(update_eval_type_sql))
    session.commit()

    return {"code": 0, "msg": "eval_history 表迁移完成"}


@with_session
def migrate_course_table(session) -> Dict:
    """
    数据库迁移函数：为 course 表新增 exam_test_case 和 exam_paper_status 字段，并初始化数据
    """
    check_column_sql = """
    PRAGMA table_info(course)
    """
    columns = session.execute(text(check_column_sql)).fetchall()
    column_names = [column[1] for column in columns]

    if 'exam_test_case' not in column_names:
        alter_table_exam_test_case_sql = """
        ALTER TABLE course ADD COLUMN exam_test_case JSON DEFAULT '{}'
        """
        session.execute(text(alter_table_exam_test_case_sql))
    
    if 'exam_paper_status' not in column_names:
        alter_table_exam_paper_status_sql = """
        ALTER TABLE course ADD COLUMN exam_paper_status VARCHAR(10) DEFAULT '未生成'
        """
        session.execute(text(alter_table_exam_paper_status_sql))
    
    session.commit()

    update_sql = """
    UPDATE course 
    SET 
        exam_test_case = '{}', 
        exam_paper_status = '未生成'
    WHERE 
        exam_test_case IS NULL OR exam_paper_status IS NULL
    """
    session.execute(text(update_sql))
    session.commit()

    return {"code": 0, "msg": "course 表迁移完成"}

@with_session
def migrate_knowledge_base_table(session) -> Dict:
    """
    数据库迁移函数：为 knowledge_base 表新增 activate 和 embedding_name 字段，
    并更新所有记录的 activate 为 '正常'，embedding_name 为 'bge-large-zh'
    """
    check_column_sql = """
    PRAGMA table_info(knowledge_base)
    """
    columns = session.execute(text(check_column_sql)).fetchall()
    column_names = [column[1] for column in columns]

    if 'activate' not in column_names:
        alter_table_activate_sql = """
        ALTER TABLE knowledge_base ADD COLUMN activate VARCHAR(10)
        """
        session.execute(text(alter_table_activate_sql))

    if 'embedding_name' not in column_names:
        alter_table_embedding_name_sql = """
        ALTER TABLE knowledge_base ADD COLUMN embedding_name VARCHAR(50)
        """
        session.execute(text(alter_table_embedding_name_sql))
    
    session.commit()

    update_sql = """
    UPDATE knowledge_base 
    SET 
        activate = '正常', 
        embedding_name = 'bge-large-zh'
    """
    session.execute(text(update_sql))
    session.commit()

    return {"code": 0, "msg": "knowledge_base 表迁移完成"}

@with_session
def migrate_knowledge_file_table(session) -> Dict:
    """
    数据库迁移函数：为 knowledge_file 表新增字段并初始化数据
    """
    # 检查字段是否存在
    check_column_sql = text("PRAGMA table_info(knowledge_file)")
    columns = session.execute(check_column_sql).fetchall()
    column_names = [column[1] for column in columns]

    # 添加字段
    if 'qa_status' not in column_names:
        session.execute(text("ALTER TABLE knowledge_file ADD COLUMN qa_status VARCHAR(10)"))
    if 'qa_count' not in column_names:
        session.execute(text("ALTER TABLE knowledge_file ADD COLUMN qa_count INTEGER"))
    if 'parse_status' not in column_names:
        session.execute(text("ALTER TABLE knowledge_file ADD COLUMN parse_status VARCHAR(10)"))
    if 'file_parse_configs' not in column_names:
        session.execute(text("ALTER TABLE knowledge_file ADD COLUMN file_parse_configs JSON"))

    session.commit()

    # 默认的 JSON 配置
    default_file_parse_configs = json.dumps({
        "image_save": False,
        "generate_query": False,
        "key_words": [],
        "separators": "W1siXuesrFxccyooPzpb5LiA5LqM5LiJ5Zub5LqU5YWt5LiD5YWr5Lmd5Y2BXXsxLDJ9fFxcZCspXFxzKlvnq6BdIiwi6ZmEXFxzKuW9lSIsIl7lj4JcXHMq6ICDXFxzKuaWh1xccyrnjK4iLCJe6ZmE6KGoXFxzKyJdLFsiXuesrFxccyooPzpb5LiA5LqM5LiJ5Zub5LqU5YWt5LiD5YWr5Lmd5Y2BXXsxLDJ9fFxcZCspXFxzKlvoioJdIiwiXumZhFxccyrlvZVcXHMqW0EtWl0iXSxbIl5cXGQrXFxzIl0sWyJeXFxkKyhcXC5cXGQrKXsxfVxccyJdLFsiXlxcZCsoXFwuXFxkKyl7Mn1cXHMiXSxbIl5cXGQrKFxcLlxcZCspezN9XFxzIl0sWyJeXFxkKyhcXC5cXGQrKXs0fVxccyJdXQ=="
    })

    # 更新字段的默认值
    update_sql = text("""
    UPDATE knowledge_file
    SET
        qa_status = '未生成',
        qa_count = 0,
        parse_status = '未解析',
        file_parse_configs = :default_file_parse_configs
    WHERE
        qa_status IS NULL OR qa_count IS NULL OR parse_status IS NULL OR file_parse_configs IS NULL
    """)
    session.execute(update_sql, {"default_file_parse_configs": default_file_parse_configs})

    # 更新所有 docs_count > 0 的记录，将 parse_status 设置为 "成功"
    update_success_sql = text("""
    UPDATE knowledge_file
    SET
        parse_status = '成功'
    WHERE
        docs_count > 0
    """)
    session.execute(update_success_sql)
    session.commit()

    return {"code": 0, "msg": "knowledge_file 表迁移完成"}



# @with_session
# def migrate_file_doc_table(session) -> Dict:
#     """
#     数据库迁移函数：为 file_doc 表新增 page_content 字段
#     """
#     # 使用 text 包裹 SQL 语句
#     check_column_sql = text("PRAGMA table_info(file_doc)")
#     columns = session.execute(check_column_sql).fetchall()
#     column_names = [column[1] for column in columns]

#     # 检查并添加字段
#     if 'page_content' not in column_names:
#         session.execute(text("ALTER TABLE file_doc ADD COLUMN page_content VARCHAR(2048)"))

#     session.commit()

#     return {"code": 0, "msg": "file_doc 表迁移完成"}


@with_session
def migrate_test_case_table(session) -> Dict:
    """
    数据库迁移函数：
    - 为 test_case 表新增 question_type 字段，并初始化数据
    - 将 test_case_type 为 "生成试题" 的记录的 course_id 设置为 NULL
    """
    # 检查字段是否存在
    check_column_sql = "PRAGMA table_info(test_case)"
    columns = session.execute(text(check_column_sql)).fetchall()
    column_names = [column[1] for column in columns]

    # 添加字段 question_type
    if 'question_type' not in column_names:
        session.execute(text("ALTER TABLE test_case ADD COLUMN question_type VARCHAR(10)"))
    
    session.commit()

    # 更新现有记录，将 question_type 设置为 "问答题"
    update_question_type_sql = """
    UPDATE test_case
    SET
        question_type = '问答题'
    WHERE
        question_type IS NULL
    """
    session.execute(text(update_question_type_sql))

    # 更新 test_case_type 为 "生成试题" 的记录，将 course_id 设置为 NULL
    update_course_id_sql = """
    UPDATE test_case
    SET
        course_id = NULL
    WHERE
        test_case_type = '生成试题'
    """
    session.execute(text(update_course_id_sql))

    session.commit()

    return {"code": 0, "msg": "test_case 表迁移完成"}


@with_session
def update_knowledge_file_with_test_case_count(session) -> Dict:
    """
    更新 knowledge_file 表中的 qa_count 和 qa_status
    根据 file_doc 表的 doc_id 在 test_case 表中匹配 test_case 数量。
    qa_count > 0 时，qa_status 设置为 '已生成'；
    qa_count <= 0 时，qa_status 设置为 '未生成'。
    """
    # 查询 file_doc 表中每个 kb_name 和 file_name 对应的所有 doc_id
    query_file_docs = text("""
    SELECT kb_name, file_name, GROUP_CONCAT(doc_id) AS doc_ids
    FROM file_doc
    GROUP BY kb_name, file_name
    """)
    file_docs = session.execute(query_file_docs).mappings().all()

    for file_doc in file_docs:
        kb_name = file_doc["kb_name"]
        file_name = file_doc["file_name"]
        doc_ids = file_doc["doc_ids"]

        if not doc_ids:
            continue

        # 将 doc_ids 转换为一个字符串列表
        doc_id_list = doc_ids.split(",")

        # 手动构造 IN 子句
        placeholders = ", ".join([f":doc_id_{i}" for i in range(len(doc_id_list))])
        query_test_case_count = text(f"""
        SELECT COUNT(*) AS test_case_count
        FROM test_case
        WHERE vs_id IN ({placeholders})
        """)
        # 创建参数字典
        params = {f"doc_id_{i}": doc_id for i, doc_id in enumerate(doc_id_list)}
        test_case_count = session.execute(query_test_case_count, params).scalar()

        # 更新 knowledge_file 表的 qa_count
        update_qa_count = text("""
        UPDATE knowledge_file
        SET
            qa_count = :test_case_count
        WHERE
            kb_name = :kb_name AND file_name = :file_name
        """)
        session.execute(
            update_qa_count,
            {
                "test_case_count": test_case_count,
                "kb_name": kb_name,
                "file_name": file_name,
            }
        )

        # 根据 qa_count 更新 qa_status
        qa_status = '已生成' if test_case_count > 0 else '未生成'
        update_qa_status = text("""
        UPDATE knowledge_file
        SET
            qa_status = :qa_status
        WHERE
            kb_name = :kb_name AND file_name = :file_name
        """)
        session.execute(
            update_qa_status,
            {
                "qa_status": qa_status,
                "kb_name": kb_name,
                "file_name": file_name,
            }
        )

    session.commit()

    return {"code": 0, "msg": "knowledge_file 表更新完成"}

@with_session
def update_file_doc_page_content_by_kb_name(session, kb_name: str) -> Dict:
    """
    根据 kb_name 更新 file_doc 表中的 page_content 字段。

    :param session: 数据库会话
    :param kb_name: 需要更新的知识库名称
    :return: 更新结果的字典
    """
    # 查询 file_doc 表中指定 kb_name 的所有记录
    query_file_docs = text("""
    SELECT kb_name, file_name, doc_id
    FROM file_doc
    WHERE kb_name = :kb_name
    """)
    file_docs = session.execute(query_file_docs, {"kb_name": kb_name}).mappings().all()

    # 如果没有找到对应的记录，返回提示信息
    if not file_docs:
        return {"code": 1, "msg": f"没有找到 kb_name={kb_name} 对应的记录"}

    # 遍历所有 file_doc 记录
    for file_doc in file_docs:
        kb_name = file_doc["kb_name"]
        file_name = file_doc["file_name"]
        doc_id = file_doc["doc_id"]

        # 获取 kb 服务实例
        kb = KBServiceFactory.get_service_by_name(kb_name)

        # 列出当前 file_name 的所有文档
        docs = kb.list_docs(file_name)

        # 转换 docs 为可用 .get() 方式访问的字典列表
        doc_dicts = []
        for doc in docs:
            doc_dict = {
                "metadata": getattr(doc, "metadata", {}),
                "page_content": getattr(doc, "page_content", ""),
            }
            doc_dicts.append(doc_dict)

        # 遍历 doc_dicts 列表，找到匹配的 doc_id
        for doc in doc_dicts:
            metadata = doc.get("metadata", {})
            vs_id = metadata.get("vs_id")
            page_content = doc.get("page_content", "")

            # 如果 vs_id 和 doc_id 匹配，则更新 page_content
            if vs_id == doc_id:
                try:
                    update_sql = text("""
                    UPDATE file_doc
                    SET page_content = :page_content
                    WHERE doc_id = :doc_id
                    """)
                    session.execute(
                        update_sql,
                        {"page_content": page_content, "doc_id": doc_id}
                    )
                    session.commit()  # 提交每次更新的事务
                    print(f"Updated page_content for doc_id={doc_id} in kb_name={kb_name}")  # Debug
                except Exception as e:
                    session.rollback()  # 回滚事务
                    print(f"Error updating doc_id={doc_id}: {e}")
                break  # 匹配成功后跳出内层循环

    return {"code": 0, "msg": f"kb_name={kb_name} 对应的 file_doc 表的 page_content 更新完成"}


from server.db.repository.layout_repository import get_image_file_list,check_and_read,analyze_layout,table_layout,_predict_text,_filter_text_res
from document_loaders.mypdfloader import find_closest_caption,find_closest_table_caption
import cv2
import os
import uuid
from urllib.parse import urlencode
import gc
import torch
import numpy as np
from PIL import Image
from reportlab.lib.utils import ImageReader
import time
from init_model import layout_predictor, text_system, table_system

def file_layout(filepath, page_start, page_end, output_dir=None, filename_without_ext=None):

    # layout_predictor, text_system, table_system = run_ocr_model()

    project_root = os.getcwd()
    
    if filename_without_ext is None:
        filename_without_ext = os.path.splitext(os.path.basename(filepath))[0]
    
    if output_dir is None:
        output_dir = os.path.join(project_root, "layout_file", filename_without_ext, "output")
    
    os.makedirs(output_dir, exist_ok=True)
    
    temp_dir = os.path.join(output_dir, "temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    image_dir = os.path.join(os.path.dirname(output_dir), "image")
    os.makedirs(image_dir, exist_ok=True)

    image_file_list = get_image_file_list(filepath)
    page_cotents = []
    figure_captions = []
    table_captions = []
    annotated_images = []
    md_content = []
    image_urls = []

    # try:
    for image_file in image_file_list:
            imgs, flag, is_pdf = check_and_read(image_file)
            if not flag:
                continue
                
            if is_pdf:
                if page_start is None:
                    page_start = 0
                else:
                    page_start = max(0, page_start-1)

                if page_end is None:
                    page_end = len(imgs)
                else:
                    page_end = min(page_end, len(imgs))

                for i in range(page_start, page_end):
                    img = imgs[i]
                    layout_res = analyze_layout(img, layout_predictor)
                    print(layout_res)
                    figure_captions.clear()
                    table_captions.clear()
                    
                    annotated_img = img.copy()
                    draw = cv2.cvtColor(np.array(annotated_img), cv2.COLOR_RGB2BGR)
                    
                    # md_content.append(f"## 第{i+1}页\n")
                    
                    for region in layout_res:
                        x1, y1, x2, y2 = region["bbox"]
                        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                        bbox = [x1, y1, x2, y2]
                        if region["label"] == "figure_caption":
                            captions = _filter_text_res(_predict_text(img, text_system), bbox)
                            for caption in captions:
                                figure_captions.append({"bbox": bbox, "text": caption["text"]})
                        
                        elif region["label"] == "table_caption":
                            captions = _filter_text_res(_predict_text(img, text_system), bbox)
                            for caption in captions:
                                table_captions.append({"bbox": bbox, "text": caption["text"]})
                    
                    page_regions = []
                    for region in layout_res:
                        x1, y1, x2, y2 = region["bbox"]
                        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                        bbox = [x1, y1, x2, y2]
                        
                        color_map = {
                            "text": (0, 255, 0),  # 绿色
                            "title": (255, 0, 0),  # 红色
                            "figure": (0, 0, 255),  # 蓝色
                            "figure_caption": (255, 255, 0),  # 黄色
                            "table": (255, 0, 255),  # 紫色
                            "table_caption": (0, 255, 255),  # 青色
                            "equation": (128, 128, 0),  # 橄榄色
                            "reference": (0, 128, 128),  # 青绿色
                            "header": (128, 0, 128),  # 紫色
                            "footer": (128, 0, 0),  # 深红色
                        }
                        color = color_map.get(region["label"], (128, 128, 128))
                        
                        cv2.rectangle(draw, (x1, y1), (x2, y2), color, 2)
                        cv2.putText(draw, region["label"], (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                        
                        if region["label"] == "header" or region["label"] == "footer":
                            continue
                        
                        # 处理标题部分
                        if region["label"] == "title":
                            res = _filter_text_res(_predict_text(img, text_system), bbox)
                            for r in res:
                                title_content = r["text"]
                                page_regions.append({
                                    "content": title_content,
                                    "type": "标题",
                                    "pageno": i + 1,
                                    "pos": bbox,
                                })

                        # 处理图片部分
                        elif region["label"] == "figure":
                            caption = find_closest_caption(figure_captions, bbox)
                            
                            # 修改图片命名逻辑，添加页码和时间戳确保唯一性
                            current_time = int(time.time() * 1000)  # 毫秒级时间戳
                            figure_filename = f"{filename_without_ext}_page{i+1}_figure{len(image_urls)}_{current_time}.jpg"
                            figure_path = os.path.join(image_dir, figure_filename)
                            
                            # 如果是 PIL 图像，需要转换为 OpenCV 格式
                            if hasattr(img, 'crop'):  # 检查是否为 PIL 图像
                                # 使用 PIL 的 crop 方法
                                figure_img = img.crop((x1, y1, x2, y2))
                                # 将 PIL 图像转换为 OpenCV 格式
                                figure_img_cv = cv2.cvtColor(np.array(figure_img), cv2.COLOR_RGB2BGR)
                                cv2.imwrite(figure_path, figure_img_cv)
                            else:
                                # 直接保存 numpy 数组
                                figure_img = img[y1:y2, x1:x2]
                                cv2.imwrite(figure_path, figure_img)
                            
                            # 构建图片URL
                            figure_relative_path = os.path.relpath(figure_path, project_root)
                            figure_url_params = urlencode({"filepath": figure_relative_path, "filename": figure_filename})
                            figure_url = f"https://ai.czy3d.com/ai-kms-api/knowledge_base/download_img?{figure_url_params}"
                            image_urls.append({"path": figure_path, "url": figure_url, "caption": caption})
                            
                            page_regions.append({
                                "content": caption if caption else "图片",
                                "type": "图片",
                                "pageno": i + 1,  # 使用当前页码
                                "pos": bbox,
                                "image_url": figure_url,
                            })

                        # 处理公式部分
                        elif region["label"] == "equation":
                            page_regions.append({
                                "content": "公式",
                                "type": "公式",
                                "pageno": i + 1,
                                "pos": bbox,
                            })

                        # 处理表格部分
                        elif region["label"] == "table":
                            table_title = find_closest_table_caption(table_captions, bbox)
                            res = table_layout(img, True, i, layout_res, table_system)
                            
                            for table in res:
                                table_content = table["res"]
                                page_regions.append({
                                    "content": str(table_content),
                                    "type": "表格",
                                    "pageno": i + 1,
                                    "pos": bbox,
                                    "tables": [table_title] if table_title else [],
                                })

                        # 处理文本内容
                        elif region["label"] in ["text"]:
                            res = _filter_text_res(_predict_text(img, text_system), bbox)
                            for r in res:
                                page_regions.append({
                                    "content": r["text"],
                                    "type": "文本",
                                    "pageno": i + 1,
                                    "pos": bbox,
                                })

                        # 处理注释内容
                        elif region["label"] in ["reference"]:
                            res = _filter_text_res(_predict_text(img, text_system), bbox)
                            for r in res:
                                page_regions.append({
                                    "content": r["text"],
                                    "type": "注释",
                                    "pageno": i + 1,
                                    "pos": bbox,
                                })
                
                    page_regions.sort(key=lambda r: (r["pos"][1], r["pos"][0]))
                    
                    page_cotents.extend(page_regions)
                    
                    print("\n=== 识别到的所有内容 ===")
                    for idx, region in enumerate(page_regions, 1):
                        print(f"\n内容块 {idx}:")
                        print(f"类型: {region['type']}")
                        print(f"页码: {region['pageno']}")
                        print(f"位置: {region['pos']}")
                        print(f"内容: {region['content'][:1000]}...")
                        if region["type"] == "图片" and "image_url" in region:
                            print(f"图片URL: {region['image_url']}")
                        if region["type"] == "表格" and "tables" in region:
                            print(f"表格标题: {region['tables']}")

                    # 将排序后的内容转换为MD格式
                    for region in page_regions:
                        if region["type"] == "标题":
                            md_content.append(f"# {region['content']}\n")
                        elif region["type"] == "文本":
                            md_content.append(f"{region['content']}\n\n")
                        elif region["type"] == "表格":
                            if "tables" in region and region["tables"]:
                                md_content.append(f"<center>{region['tables'][0]}</center>\n\n")
                            md_content.append(f"{convert_table_to_markdown(region['content'])}\n\n")
                        elif region["type"] == "图片":
                            if "image_url" in region:
                                md_content.append(f"![图片]({region['image_url']})\n\n")
                                if region.get("content") and region["content"] != "图片":
                                    md_content.append(f"<center>{region['content']}</center>\n\n")
                            else:
                                md_content.append(f"![图片]\n\n")
                        elif region["type"] == "公式":
                            md_content.append(f"*公式*\n\n")
                        elif region["type"] == "注释":
                            md_content.append(f"> {region['content']}\n\n")
                    
                    # 保存带标注的图片
                    annotated_img_path = os.path.join(temp_dir, f"image_annotated_page{i+1}.jpg")
                    cv2.imwrite(annotated_img_path, draw)
                    annotated_images.append(annotated_img_path)
            else:
                # 处理单张图片
                img = imgs[0]
                layout_res = analyze_layout(img, layout_predictor)
                
                figure_captions.clear()
                table_captions.clear()
                
                annotated_img = img.copy()
                draw = cv2.cvtColor(np.array(annotated_img), cv2.COLOR_RGB2BGR)
                
                for region in layout_res:
                    x1, y1, x2, y2 = region["bbox"]
                    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                    bbox = [x1, y1, x2, y2]
                    if region["label"] == "figure_caption":
                        captions = _filter_text_res(_predict_text(img, text_system), bbox)
                        for caption in captions:
                            figure_captions.append({"bbox": bbox, "text": caption["text"]})
                    
                    elif region["label"] == "table_caption":
                        captions = _filter_text_res(_predict_text(img, text_system), bbox)
                        for caption in captions:
                            table_captions.append({"bbox": bbox, "text": caption["text"]})
                
                page_regions = []
                for region in layout_res:
                    x1, y1, x2, y2 = region["bbox"]
                    x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                    bbox = [x1, y1, x2, y2]
                    
                    color_map = {
                        "text": (0, 255, 0),  # 绿色
                        "title": (255, 0, 0),  # 红色
                        "figure": (0, 0, 255),  # 蓝色
                        "figure_caption": (255, 255, 0),  # 黄色
                        "table": (255, 0, 255),  # 紫色
                        "table_caption": (0, 255, 255),  # 青色
                        "equation": (128, 128, 0),  # 橄榄色
                        "reference": (0, 128, 128),  # 青绿色
                        "header": (128, 0, 128),  # 紫色
                        "footer": (128, 0, 0),  # 深红色
                    }
                    color = color_map.get(region["label"], (128, 128, 128))  # 默认灰色
                    
                    # 绘制矩形框和标签
                    cv2.rectangle(draw, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(draw, region["label"], (x1, y1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)
                    
                    # 跳过页眉和页脚
                    if region["label"] == "header" or region["label"] == "footer":
                        continue
                    
                    # 处理标题部分
                    if region["label"] == "title":
                        res = _filter_text_res(_predict_text(img, text_system), bbox)
                        for r in res:
                            title_content = r["text"]
                            page_regions.append({
                                "content": title_content,
                                "type": "标题",
                                "pageno": 1,
                                "pos": bbox,
                            })

                    # 处理图片部分
                    elif region["label"] == "figure":
                        caption = find_closest_caption(figure_captions, bbox)
                        
                        figure_img = img[y1:y2, x1:x2]
                        figure_filename = f"{filename_without_ext}_figure{len(image_urls)}.jpg"
                        figure_path = os.path.join(image_dir, figure_filename)
                        cv2.imwrite(figure_path, figure_img)
                        
                        figure_relative_path = os.path.relpath(figure_path, project_root)
                        figure_url_params = urlencode({"filepath": figure_relative_path, "filename": figure_filename})
                        figure_url = f"https://ai.czy3d.com/ai-kms-api/knowledge_base/download_img?{figure_url_params}"
                        image_urls.append({"path": figure_path, "url": figure_url, "caption": caption})
                        
                        page_regions.append({
                            "content": caption if caption else "图片",
                            "type": "图片",
                            "pageno": 1,
                            "pos": bbox,
                            "image_url": figure_url,
                        })
                
                page_regions.sort(key=lambda r: (r["pos"][1], r["pos"][0]))
                
                page_cotents.extend(page_regions)
                
                for region in page_regions:
                    if region["type"] == "标题":
                        md_content.append(f"# {region['content']}\n")
                    elif region["type"] == "文本":
                        md_content.append(f"{region['content']}\n\n")
                    elif region["type"] == "表格":
                        if "tables" in region and region["tables"]:
                            md_content.append(f"<div align=\"center\"><b>{region['tables'][0]}</b></div>\n\n")
                        md_content.append(f"{convert_table_to_markdown(region['content'])}\n\n")
                    elif region["type"] == "图片":
                        if "image_url" in region:
                            md_content.append(f"![图片]({region['image_url']})\n\n")
                            if region.get("content") and region["content"] != "图片":
                                md_content.append(f"<div align=\"center\"><b>{region['content']}</b></div>\n\n")
                        else:
                            md_content.append(f"![图片]\n\n")
                    elif region["type"] == "公式":
                        md_content.append(f"*公式*\n\n")
                    elif region["type"] == "注释":
                        md_content.append(f"> {region['content']}\n\n")
                
                annotated_img_path = os.path.join(temp_dir, "image_annotated.jpg")
                cv2.imwrite(annotated_img_path, draw)
                annotated_images.append(annotated_img_path)

    # finally:
    #     del layout_predictor
    #     del text_system
    #     del table_system
        
    #     if torch.cuda.is_available():
    #         torch.cuda.empty_cache()
        
    #     gc.collect()
    
    pdf_path = os.path.join(output_dir, f"{filename_without_ext}_annotated.pdf")
    create_pdf_from_images(annotated_images, pdf_path)
    
    md_path = os.path.join(output_dir, f"{filename_without_ext}_content.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("".join(md_content))
    
    # 清理临时文件
    for img_path in annotated_images:
        if os.path.exists(img_path):
            os.remove(img_path)
    if os.path.exists(temp_dir):
        os.rmdir(temp_dir)
    
    pdf_relative_path = os.path.relpath(pdf_path, project_root)
    md_relative_path = os.path.relpath(md_path, project_root)
    
    pdf_url_request_parameters = urlencode({"filepath": pdf_relative_path, "filename": f"{filename_without_ext}_annotated.pdf"})
    md_url_request_parameters = urlencode({"filepath": md_relative_path, "filename": f"{filename_without_ext}_content.md"})
    
    pdf_url = f"knowledge_base/download_file?{pdf_url_request_parameters}"
    md_url = f"knowledge_base/download_file?{md_url_request_parameters}"
    
    return {
        "pdf_url": pdf_url,
        "md_url": md_url,
        "md_content": "".join(md_content),
    }

def convert_table_to_markdown(table_content):
    """将表格内容转换为Markdown格式"""
    try:
        if isinstance(table_content, str) and table_content.startswith("<html>"):
            from bs4 import BeautifulSoup
            
            soup = BeautifulSoup(table_content, 'html.parser')
            table = soup.find('table')
            
            if not table:
                return table_content
            
            md_table = []
            
            headers = []
            header_row = table.find('thead')
            if header_row:
                for cell in header_row.find_all(['th', 'td']):
                    headers.append(cell.get_text().strip())
            else:
                first_row = table.find('tr')
                if first_row:
                    for cell in first_row.find_all(['th', 'td']):
                        headers.append(cell.get_text().strip())
            
            if headers:
                md_table.append("| " + " | ".join(headers) + " |")
                md_table.append("| " + " | ".join(["---"] * len(headers)) + " |")
            
            rows = table.find_all('tr')
            start_idx = 1 if header_row else 1
            
            for row in rows[start_idx:]:
                cells = []
                for cell in row.find_all(['th', 'td']):
                    cells.append(cell.get_text().strip())
                if cells:
                    md_table.append("| " + " | ".join(cells) + " |")
            
            return "\n".join(md_table)
        
        elif isinstance(table_content, str):
            table_content = table_content.replace("'", "").replace("[", "").replace("]", "")
            rows = table_content.split("), (")
            rows = [row.replace("(", "").replace(")", "").split(", ") for row in rows]
        else:
            rows = table_content
        
        if not rows:
            return ""
        
        md_table = []
        
        # 表头
        header = rows[0]
        md_table.append("| " + " | ".join(header) + " |")
        md_table.append("| " + " | ".join(["---"] * len(header)) + " |")
        
        # 表格内容
        for row in rows[1:]:
            md_table.append("| " + " | ".join(row) + " |")
        
        return "\n".join(md_table)
    except Exception as e:
        print(f"表格转换错误: {e}")
        # 如果解析失败，返回原始内容
        return str(table_content)
    
def create_pdf_from_images(image_paths, output_path):
    """将多张图片合并为一个PDF文件"""
    try:
        import img2pdf
        
        valid_images = [img_path for img_path in image_paths if os.path.exists(img_path)]
        
        if not valid_images:
            print("没有有效的图像可处理")
            return
        
        with open(output_path, "wb") as f:
            f.write(img2pdf.convert(valid_images))
        
        print(f"PDF文件已保存: {output_path}")
    except Exception as e:
        print(f"创建PDF时出错: {e}")

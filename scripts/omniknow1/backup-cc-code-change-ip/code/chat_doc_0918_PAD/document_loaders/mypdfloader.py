import sys
sys.path.append("./")
from typing import Any, List, Union
from langchain.document_loaders.unstructured import UnstructuredFileLoader
import tqdm
import re
import json
from langchain.docstore.document import Document
from text_splitter.chinese_chapter_recursive_splitter import ChineseChapterRecursiveSplitter
from configs.kb_config import CHUNK_SIZE, OVERLAP_SIZE
from copy import deepcopy
import os
from pathlib import Path
import pdfplumber
import math
import uuid
from server.utils import gen_question
from server.db.repository.layout_repository import get_image_file_list,check_and_read,analyze_layout,table_layout,_predict_text,_filter_text_res
import cv2
import fitz


default_parse_file_config={"page_start":0}
GENERATE_OUTPUT_JSON =True
SAVE_IMAGE = True
GENERATE_QUERY =False
BLOCK_MAX_LEN =4*512
#可以传进来
content_start_page_index =2
# "AP1000核电厂概述","反应堆系统","AP1000反应堆冷却剂系统","非能动堆芯冷却系统","安全壳和安全壳系统","辅助系统","蒸汽动力转换系统","电气系统","仪表控制系统","AP1000安全分析"
PAGE_HEAD_LIST =PAGE_HEAD_LIST =["非能动安全先进核电厂AP1000"]
Y_TOLERANCE = 2
key_word_dict = {
    "维修":"维修",
    "故障":"故障",
    "参数":"参数",
    "属性":"属性",
    "操作":"操作",
    "使用":"使用",
    "步骤":"步骤"
}

def get_pdf_toc(pdf_path):
    import fitz
    doc = fitz.open(pdf_path)
    tocs = doc.get_toc()
    tocs_dict = {}
    for toc in tocs:
        # print("toc",toc)
        tocs_dict[toc[1]] = toc[0]
    return tocs_dict

# result = get_pdf_toc("/home/star/projects/chat_doc/knowledge_base/test_nuclear/content/非能动安全先进核电厂AP1000.pdf")
# print(result)


def in_table_index(location, tables):
    if not tables:
        return -1
    x0, y0, x1, y1 = location
    boundings = [table.bbox for table in tables]
    for index, bounding in enumerate(boundings):
        b_x0, b_y0, b_x1, b_y1 = bounding
        if b_x0 < x0 and b_y0 < y0 and b_x1 > x1 and b_y1 > y1:
            return index
    return -1


def remove_special_chars(text:str) -> str:
    special_chars = r"[-.]{2,}|[■…]"
    text = re.sub(special_chars, "", text)
    return text

def potential_title_pos(text):
    if len(text) == 0:
        return -1
    index_of_newline = text.find('\n')
    return index_of_newline

def is_title(title_level_list,txt,catalogues) -> bool:
    # MOD BY LIUBIN. 修改为pattern_list
    title_level =-1
    match = None
    for title_level, title_pattern_list in enumerate(title_level_list):
        for pattern in title_pattern_list:
            match = re.search(pattern=pattern, string=txt)
            print(repr(txt),"pattern:",pattern,match)
            if match:
                if "附录" in txt.replace(" ", "") or "参考文献" in txt.replace(" ", ""):
                    return match, len(title_level_list) - 1 - title_level
                break
            
        if match:
            break

    # 判断剩下的一行文本中是否有中文标点符号 可以包含？
    # “”\u201c\u201d
    #：\uff1a
    # 黑名单
    # 。，；《》！·%[].,
    chinese_punctuation = r'[\u3002\uff0c\uff1b\u300a\u300b\uff01\u00b7\u002c\u0025\u002f\u005b\u005d\u002e]'
    
    #排除1.159 1.285这种情况
    chinese_char_re = r'[\u4e00-\u9fa5]' 
    en_char_re =r'[a-zA-Z]'
    if match and (not re.search(chinese_punctuation, txt[match.end():])) and (re.search(chinese_char_re,txt[match.end():]) or re.search(en_char_re,txt[match.end():])):
        return match,len(title_level_list)-1-title_level
    #如果还没有比配到，看看是不是在目录结构中
    for catalogue in catalogues:
        if txt.strip() in catalogue:
            return True,0
    return None,-1,

def is_page_footer(txt):
    if txt.isdigit():
        return True
    
def is_catalogue_line(txt):
    txt =txt.strip()
    if txt.replace(" ","") in ["目录","前言","CONTENTS"]:
        return True
    # catalogue_entry_pattern = re.compile(r'(…)*(\s\S)*\d')  #^(\s)*(…)+(\s)*\d$
    catelogue_re_list = [r'^.*\…{2,}.*\d$',r'^.*\.{6,}\s*\(*\d\)*'] 
    for catelogue_re in catelogue_re_list:
        catalogue_entry_pattern = re.compile(catelogue_re)
        # 检查文本是否匹配目录单模式
        match = catalogue_entry_pattern.match(txt)
        if match:
            return True
    
    return False

    
def is_page_header(txt,file_name):
    """"
    第几章 xxx 10
    10 书名
    书名 10
    10｜书名
    ｜223
    """
    repr_str_list= [r'\b^第\s*(?:[一二三四五六七八九十]{1,2}|\d+)\s*[章]\s*\S*\s*\d',
                    r'\b^附 录\S*\s*\d',
                    r'\b^参 考 文 献\S*\s*\d',
                    r'\b^\d(\s*|｜)'+file_name.replace("“","\“").replace("”","\”"),
                    r'^.*｜\d+$',
                    r'\d+｜\S+'
                    ]
    for repr_str in repr_str_list:
        # print("page_header ",repr(txt),"pattern:",repr(repr_str),re.match(repr_str,txt))
        if re.match(repr_str,txt):
            return True
    
    return False

def center_pos(pos):
    return ((pos[0]+pos[2])/2,(pos[1]+pos[3])/2)

def bottom_center_pos(pos):
    return ((pos[0]+pos[2])/2,pos[3])

def top_center_pos(pos):
    return ((pos[0] + pos[2]) / 2, pos[1])

def find_image_name(filename,page_num,image_bbox,_g_image_name_list,_g_image_name_pos_list,page_height):
    """
    最近两页内容
    图标题必须在图之下
    """
    image_name_list =[]
    image_name_pos_list =[]
    
    #当前页中找title，优化查找速度
        
    image_name_list.extend(_g_image_name_list)
    image_name_pos_list.extend(_g_image_name_pos_list)

    if len(image_name_list) != len(image_name_pos_list):
        # image_name =  str(page_num)+"_"+ str(uuid.uuid4())
        # return image_name
        return None
    
    image_center_pos = bottom_center_pos(image_bbox)
    min_dis = 100000
    min_index = -1
    for image_name_index,image_name_pos in enumerate(image_name_pos_list):
        image_name_center_pos = center_pos(image_name_pos)
        
        if image_center_pos[1]>image_name_center_pos[1]:
            continue
        _dis = math.sqrt(math.pow((image_center_pos[0] - image_name_center_pos[0]), 2) + math.pow((image_center_pos[1] - image_name_center_pos[1]), 2))
        if _dis < min_dis:
            min_dis = _dis
            min_index = image_name_index
    if min_index !=-1 and min_dis < page_height:
        ret = str(page_num)+"_"+image_name_list[min_index]
        #去除文件名中包含的特殊字符
        ret = ret.replace("/",' ')
        return ret
    else:
        # new_image_name =  str(page_num)+"_"+ str(uuid.uuid4())
        # return new_image_name
        return None
        
def create_documents(chapter, title_stack, title_prefix, metadata: dict) -> List[Document]:
    prefix = ""
    for i, sub_title in enumerate(title_stack):
        if sub_title:
            prefix += title_prefix*i+sub_title
    prefix = re.sub(r'\s+', '', prefix)
    metadata['titles'] = prefix
    
    # if len(chapter) < OVERLAP_SIZE:
    #     return []
    # if len(chapter) > CHUNK_SIZE:
    #     chunks = [chapter[:CHUNK_SIZE]]
    #     chunks.extend([chapter[i-OVERLAP_SIZE:i+CHUNK_SIZE] for i in range(CHUNK_SIZE, len(chapter), CHUNK_SIZE)])
    #     docs = [Document(page_content=chunk, metadata=deepcopy(metadata)) for chunk in chunks]
    #     return docs
    docs = [Document(page_content=chapter, metadata=deepcopy(metadata))]
    metadata['images'] = []
    metadata['tables'] = []
    
    return docs

def split_titles(txt,ori_x0, ori_y0, ori_x1, ori_y1):
    ts = str(txt).split(" 图")
    ts_len = len(txt)
    tchar_width = (ori_x1-ori_x0)/ts_len
    ret = []
    for index,t in enumerate(ts):
        t = t.strip()
        
        if len(t) > 0:
            start_pos = str(txt).find(t)
            if index > 0:
                t = "图"+t
            ret.append((t,(ori_x0+start_pos*tchar_width, ori_y0, ori_x0+(start_pos+len(t))*tchar_width, ori_y1)))
    return ret
            
def post_split(text):
    """
    把标题中的空格和换行去掉
    把文中多余的空格/换行替换成单一空格/换行    
    """
    # text = text.replace('\n', title_split, 1)
    # title_pos = text.find(title_split)
    # if title_pos != -1:
    #     text = re.sub(r'\s+', '', text[:title_pos]) + text[title_pos:]
    text = remove_special_chars(text)
    # text = re.sub(r'\<image:.*?\>', '', text)
    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r' ?\n ?', '\n', text)
    text = re.sub(r'\n{2,}', '\n', text)
    text = remove_newlines_between_chinese(text)
    return text

def detect_merged_cells(table_data):
    """
    检测表格中的合并单元格
    返回合并信息的字典
    """
    if not table_data or len(table_data) == 0:
        return {}
    
    merged_cells = {}
    rows = len(table_data)
    
    for row_idx in range(rows):
        if not table_data[row_idx]:
            continue
        cols = len(table_data[row_idx])
        
        for col_idx in range(cols):
            cell_value = table_data[row_idx][col_idx]
            
            # 检查水平合并（colspan）
            colspan = 1
            for next_col in range(col_idx + 1, cols):
                if (table_data[row_idx][next_col] == cell_value and 
                    cell_value is not None and str(cell_value).strip() != ""):
                    colspan += 1
                else:
                    break
            
            # 检查垂直合并（rowspan）
            rowspan = 1
            for next_row in range(row_idx + 1, rows):
                if (next_row < len(table_data) and 
                    col_idx < len(table_data[next_row]) and
                    table_data[next_row][col_idx] == cell_value and 
                    cell_value is not None and str(cell_value).strip() != ""):
                    rowspan += 1
                else:
                    break
            
            # 记录合并信息
            if colspan > 1 or rowspan > 1:
                merged_cells[(row_idx, col_idx)] = {
                    'colspan': colspan,
                    'rowspan': rowspan,
                    'value': cell_value
                }
    
    return merged_cells

def clean_table_data_with_merge(table_data):
    """
    清理表格数据并处理合并单元格
    """
    if not table_data:
        return [], {}
    
    # 首先清理数据
    cleaned_data = []
    for row in table_data:
        if row is None:
            continue
        cleaned_row = []
        for cell in row:
            if cell is None or cell == "None":
                cleaned_row.append("")
            else:
                cleaned_cell = str(cell).replace('\n', ' ').strip()
                cleaned_row.append(cleaned_cell)
        cleaned_data.append(cleaned_row)
    
    # 过滤掉完全空白的行
    cleaned_data = [row for row in cleaned_data if any(cell.strip() for cell in row)]
    
    # 检测合并单元格
    merged_cells = detect_merged_cells(cleaned_data)
    
    return cleaned_data, merged_cells

def table_to_html_with_merge(table_data):
    """
    将表格数据转换为HTML格式，支持合并单元格
    """
    if not table_data or len(table_data) == 0:
        return ""
    
    # 清理数据并检测合并单元格
    cleaned_data, merged_cells = clean_table_data_with_merge(table_data)
    if not cleaned_data:
        return ""
    
    html_parts = ['<table border="1" style="border-collapse: collapse; width: 100%;">']
    
    # 记录已处理的单元格（被合并的单元格不需要再次输出）
    processed_cells = set()
    
    # 处理表头（假设第一行是表头）
    if len(cleaned_data) > 0:
        html_parts.append('<thead><tr>')
        for col_idx, cell in enumerate(cleaned_data[0]):
            if (0, col_idx) in processed_cells:
                continue
                
            cell_attrs = 'style="padding: 8px; text-align: left; background-color: #f2f2f2;"'
            
            # 检查是否有合并信息
            if (0, col_idx) in merged_cells:
                merge_info = merged_cells[(0, col_idx)]
                if merge_info['colspan'] > 1:
                    cell_attrs += f' colspan="{merge_info["colspan"]}"'
                    # 标记被合并的单元格
                    for c in range(col_idx + 1, col_idx + merge_info['colspan']):
                        processed_cells.add((0, c))
                
                if merge_info['rowspan'] > 1:
                    cell_attrs += f' rowspan="{merge_info["rowspan"]}"'
                    # 标记被合并的单元格
                    for r in range(1, merge_info['rowspan']):
                        processed_cells.add((r, col_idx))
            
            html_parts.append(f'<th {cell_attrs}>{cell}</th>')
        html_parts.append('</tr></thead>')
    
    # 处理表格主体
    if len(cleaned_data) > 1:
        html_parts.append('<tbody>')
        for row_idx in range(1, len(cleaned_data)):
            html_parts.append('<tr>')
            for col_idx, cell in enumerate(cleaned_data[row_idx]):
                if (row_idx, col_idx) in processed_cells:
                    continue
                    
                cell_attrs = 'style="padding: 8px;"'
                
                # 检查是否有合并信息
                if (row_idx, col_idx) in merged_cells:
                    merge_info = merged_cells[(row_idx, col_idx)]
                    if merge_info['colspan'] > 1:
                        cell_attrs += f' colspan="{merge_info["colspan"]}"'
                        # 标记被合并的单元格
                        for c in range(col_idx + 1, col_idx + merge_info['colspan']):
                            processed_cells.add((row_idx, c))
                    
                    if merge_info['rowspan'] > 1:
                        cell_attrs += f' rowspan="{merge_info["rowspan"]}"'
                        # 标记被合并的单元格
                        for r in range(row_idx + 1, row_idx + merge_info['rowspan']):
                            processed_cells.add((r, col_idx))
                
                html_parts.append(f'<td {cell_attrs}>{cell}</td>')
            html_parts.append('</tr>')
        html_parts.append('</tbody>')
    
    html_parts.append('</table>')
    return ''.join(html_parts)

def remove_newlines_between_chinese(text):
    # 正则表达式，匹配两个汉字之间的换行符，但是如果其中一个汉字是'图'或者'表'则不管
    # pattern = re.compile(r'((?![图表])[一-龥])(\s+)((?![图表])[一-龥])')
    pattern = re.compile(r'(?<=[^\W\d图表])\s+(?=[^\W\d图表])')
    return pattern.sub(r'', text).strip()
    return pattern.sub(r'\1\2', text).strip()

def filter_txt(txt):
    txt = txt.strip()
    start_char =["△","▲","☆","最新 "]
    for delete_char in start_char:
        if str(txt).startswith(delete_char):
            txt = txt[len(start_char):]
    return txt

def merge_pos(pos1,pos2):
    return (min(pos1[0],pos2[0]),min(pos1[1],pos2[1]),max(pos1[2],pos2[2]),max(pos1[3],pos2[3]))


import random


def is_pdf_scanned(filepath, image_threshold=0.7):

    doc = fitz.open(filepath)
    total_pages = len(doc)

    if total_pages < 2:
        pages_to_check = range(total_pages)
    else:
        pages_to_check = random.sample(range(total_pages), 2)

    for page_num in pages_to_check:
        page = doc.load_page(page_num)

        text = page.get_text()
        has_text = text and len(text.strip()) > 20

        image_list = page.get_images(full=True)
        has_large_image = False

        for img in image_list:
            xref = img[0]
            img_info = page.get_image_info(xref)

            img_width = img_height = 0

            if isinstance(img_info, dict):
                img_width = img_info.get('width', 0)
                img_height = img_info.get('height', 0)

            elif isinstance(img_info, list):
                for sub_img_info in img_info:
                    if isinstance(sub_img_info, dict):
                        img_width = sub_img_info.get('width', 0)
                        img_height = sub_img_info.get('height', 0)
                        break
            else:
                continue

            if img_width == 0 or img_height == 0:
                continue

            page_width, page_height = page.rect.width, page.rect.height
            page_area = page_width * page_height
            img_area = img_width * img_height

            if img_area / page_area > image_threshold:
                has_large_image = True
                break

        if has_text:
            return False

        if has_large_image:
            return True

    return False



def find_closest_caption(captions, figure_bbox):
    """
    根据 figure_bbox 找到最近的 figure_caption.
    """
    min_distance = float('inf')
    closest_caption = None

    # 计算图像底部中心点
    figure_center_pos = bottom_center_pos(figure_bbox)

    for caption in captions:
        caption_bbox = caption["bbox"]
        caption_center_pos = center_pos(caption_bbox)

        # 计算图像和标题中心的欧几里得距离
        distance = math.sqrt(math.pow((figure_center_pos[0] - caption_center_pos[0]), 2) + 
                             math.pow((figure_center_pos[1] - caption_center_pos[1]), 2))


        # 只需确保标题在图像的下方且距离最短
        if caption_center_pos[1] > figure_center_pos[1] and distance < min_distance:
            min_distance = distance
            closest_caption = caption["text"]

    return closest_caption


def find_closest_table_caption(captions, table_bbox):
    """
    根据 table_bbox 找到最近的 table_caption.
    """
    min_distance = float('inf')
    closest_caption = None

    # 计算表格顶部中心点
    table_center_pos = top_center_pos(table_bbox)

    for caption in captions:
        caption_bbox = caption["bbox"]
        caption_center_pos = center_pos(caption_bbox)

        # 计算表格和标题中心的欧几里得距离
        distance = math.sqrt(math.pow((table_center_pos[0] - caption_center_pos[0]), 2) + 
                             math.pow((table_center_pos[1] - caption_center_pos[1]), 2))

        # 只需确保标题在表格的上方且距离最短
        if caption_center_pos[1] < table_center_pos[1] and distance < min_distance:
            min_distance = distance
            closest_caption = caption["text"]

    return closest_caption

import requests

def get_image_description(image_path):
    """
    调用描述服务获取图片描述。
    """
    server_url = "http://192.168.21.111:7863/describe"
    payload = {"image_path": image_path}

    try:
        response = requests.post(server_url, json=payload)
        if response.status_code == 200:
            result = response.json()
            return result.get("description", "No description")
        else:
            print(f"Error: {response.status_code}, {response.text}")
            return None
    except Exception as e:
        print(f"Failed to call the service: {e}")
        return None

from queue import Queue
import gc
import torch
import threading

# 添加文件处理锁
file_processing_lock = threading.Lock()
progress_queue = Queue()



# layout_predictor,text_system,table_system = run_ocr_model()
# layout_predictor,text_system,table_system = None,None,None

def update_progress(current_page, total_pages, kb_name, file_name):
    progress = f"{min((current_page / total_pages) * 100, 100):.2f}%"
    progress_queue.put({
                    "kb_name": kb_name,
                    "file_name": file_name,
                    "progress": progress,
                    "current_page": current_page,
                    "total_pages": total_pages
                })

from init_model import layout_predictor, text_system, table_system

def layout_pdf(filepath, title_level_list, catalogue_lines, filename, parse_file_config):
    # global layout_predictor, text_system, table_system
    
    # 使用锁保护整个文件处理过程
    with file_processing_lock:
        # if layout_predictor is None or text_system is None or table_system is None:
        #     layout_predictor, text_system, table_system = run_ocr_model()

        # 获取图片文件列表
        image_file_list = get_image_file_list(filepath)

        # 从 parse_file_config 获取页码范围
        content_start_page_index = parse_file_config.get("page_start",None)
        if content_start_page_index is None:
            content_start_page_index = 0
        else:
            content_start_page_index = content_start_page_index - 1
        content_end_page_index = parse_file_config.get("page_end",None)


        page_cotents = []

        # 初始化保存图片的目录
        image_save_dir = str(Path(filepath).parent.parent) + "/image/" + filename
        if not os.path.exists(image_save_dir):
            os.makedirs(image_save_dir)

        file_name = Path(filepath).name
        kb_name = Path(filepath).parent.parent.name
        current_page = 1

        # 遍历图片文件列表
        # try:
        for image_file in image_file_list:
                # 读取图片或PDF文件
                imgs, flag, is_pdf = check_and_read(image_file)

                if is_pdf:
                    page_start = max(0, content_start_page_index)
                    page_end = min(content_end_page_index, len(imgs)) if content_end_page_index is not None else len(imgs)
                    total_pages = page_end - page_start
                    total_pages = min(total_pages,len(imgs))
                    # 遍历指定页范围的图片
                    for i in range(page_start, page_end):
                        img = imgs[i]
                        layout_res = analyze_layout(img,layout_predictor)

                        figure_captions = []
                        table_captions = []

                        for region in layout_res:
                            x1, y1, x2, y2 = region["bbox"]
                            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                            bbox = [x1, y1, x2, y2]
                            if region["label"] == "figure_caption":
                                captions = _filter_text_res(_predict_text(img,text_system), bbox)
                                for caption in captions:
                                    figure_captions.append({"bbox": bbox, "text": caption["text"]})
                            
                            elif region["label"] == "table_caption":
                                captions = _filter_text_res(_predict_text(img,text_system), bbox)
                                for caption in captions:
                                    table_captions.append({"bbox": bbox, "text": caption["text"]})                             
                    
                        # 获取页面尺寸
                        img_height, img_width = img.shape[:2]
                        
                        for region in layout_res:
                            x1, y1, x2, y2 = region["bbox"]
                            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
                            bbox = [x1, y1, x2, y2]
                            
                            # 归一化坐标，与非版面分析方式保持一致
                            normalized_pos = (x1/img_width, y1/img_height, x2/img_width, y2/img_height)

                            # 跳过页眉和页脚
                            if region["label"] == "header" or region["label"] == "footer":
                                continue
                            
                            # 处理标题部分
                            if region["label"] == "title":
                                res = _filter_text_res(_predict_text(img,text_system), bbox)

                                for r in res:
                                    title_content = r["text"]

                                    # 使用正则表达式对提取的标题文本进行分级
                                    match, title_level = is_title(title_level_list, title_content, catalogue_lines)
                                    print("Match:", match, "Title Level:", title_level)
                                    if match is not None:
                                        page_cotents.append({
                                            "content": title_content,
                                            "type": "TITLE",
                                            "TITLE_LEVEL": title_level,
                                            "pageno": i + 1,
                                            "pos": normalized_pos,
                                            "tables": [],
                                            "image_title": [],
                                            "images": [],
                                            "images_path": []
                                        })

                            # 处理图片部分
                            elif region["label"] == "figure":
                                image_bbox = img[y1:y2, x1:x2]
                                caption = find_closest_caption(figure_captions, bbox)
                                # if caption:
                                #     image_name = f"{i + 1}_{caption}.jpg"
                                # else:
                                #     image_name = f"{i + 1}_image_{uuid.uuid4()}.jpg"
                                # image_save_path = os.path.join(image_save_dir, image_name)
                                # cv2.imwrite(image_save_path, image_bbox)

                                if not caption:
                                    temp_image_path = os.path.join(image_save_dir, f"temp_{uuid.uuid4()}.jpg")
                                    cv2.imwrite(temp_image_path, image_bbox)
                                    caption = get_image_description(temp_image_path)
                                    if not caption:
                                        caption = "No description"
                                    os.remove(temp_image_path)

                                image_name = f"{i + 1}_{caption}.jpg"
                                image_save_path = os.path.join(image_save_dir, image_name)
                                cv2.imwrite(image_save_path, image_bbox)
                                
                                page_cotents.append({
                                    "content": "",
                                    "type": "IMAGE",
                                    "pageno": i + 1,
                                    "pos": normalized_pos,
                                    "images": [caption] if caption else [],
                                    "image_title": [],
                                    "tables": [],
                                    "images_path": [image_save_path]
                                })
                                
                            # 处理公式部分
                            elif region["label"] == "equation":
                                equation_bbox = img[y1:y2, x1:x2]
                                equation_name = f"{i + 1}_equation_{uuid.uuid4()}.jpg"
                                equation_save_path = os.path.join(image_save_dir, equation_name)
                                cv2.imwrite(equation_save_path, equation_bbox)

                                page_cotents.append({
                                    "content": "",
                                    "type": "IMAGE",
                                    "pageno": i + 1,
                                    "pos": normalized_pos,
                                    "images": [],
                                    "image_title": [],
                                    "tables": [],
                                    "images_path": [equation_save_path]
                                })

                            # 处理表格部分
                            elif region["label"] == "table":
                                table_title = find_closest_table_caption(table_captions, bbox)
                                res = table_layout(img, True, i, layout_res,table_system)

                                for table in res:
                                    table_content = table["res"]
                                    page_cotents.append({
                                        "content": str(table_content),
                                        "type": "TABLE",
                                        "pageno": i + 1,
                                        "pos": normalized_pos,
                                        "tables": [table_title] if table_title else [],
                                        "image_title": [],
                                        "images": [],
                                        "images_path": []
                                    })

                            # 处理文本内容
                            elif region["label"] in ["text", "reference"]:
                                res = _filter_text_res(_predict_text(img,text_system), bbox)
                                for r in res:
                                    page_cotents.append({
                                        "content": r["text"],
                                        "type": "TXT",
                                        "pageno": i + 1,
                                        "pos": normalized_pos,
                                        "tables": [],
                                        "image_title": [],
                                        "images": [],
                                        "images_path": []
                                    })

                        update_progress(current_page, total_pages, kb_name, file_name)
                        current_page += 1
                        # progress = f"{min(((i + 1) / total_pages) * 100, 100):.2f}%"
                        # progress_queue.put({
                        #     "kb_name": kb_name,
                        #     "file_name": file_name,
                        #     "progress": progress,
                        #     "current_page": i + 1,
                        #     "total_pages": total_pages
                        # }) 
        # finally:
        #     del layout_predictor
        #     del text_system
        #     del table_system
            
        #     if torch.cuda.is_available():
        #         torch.cuda.empty_cache()
            
        #     gc.collect()
            # model_manager.release_gpu_memory()
        page_cotents.sort(key=lambda r: (r["pageno"], r["pos"][1], r["pos"][0]))
        # page_cotents.sort(key=lambda r: (r["pageno"], r["pos"][0], r["pos"][1]))

        # print(page_cotents)
        return page_cotents


def parse_pdf_content(filepath,title_level_list,catalogue_lines,parse_file_config):
    page_cotents = []
    filename = str(os.path.basename(filepath))
    last_dot_index = filename.rfind(".")
    filename = filename[:last_dot_index]

    if is_pdf_scanned(filepath):
        page_cotents=layout_pdf(filepath,title_level_list,catalogue_lines,filename,parse_file_config)
        return page_cotents
            
    file_name = Path(filepath).name
    kb_name = Path(filepath).parent.parent.name
    current_page = 1
    pages = pdfplumber.open(filepath).pages
    
    content_start_page_index = parse_file_config.get("page_start",None)
    if content_start_page_index is None or content_start_page_index <= 0:
        content_start_page_index = 0
    else:
        content_start_page_index = content_start_page_index - 1

    content_end_page_index = parse_file_config.get("page_end",len(pages))
    if content_end_page_index <= 0:
        content_end_page_index = len(pages)

    if content_start_page_index > content_end_page_index:
        content_start_page_index = 0
 
    total_pages = content_end_page_index - content_start_page_index
    total_pages = min(total_pages,len(pages))
    #文档是否是表格,默认是True
    config_is_table = True
    #是否要剔除标题的序列号,默认是True
    config_is_replace_title_no = False
    
    b_unit = tqdm.tqdm(total=total_pages, desc="parse page index: 0")

    txt, x0, y0, x1, y1 = '', 0.1, 0.1, 0.9, 0.9

    for page_num in range(content_start_page_index,content_end_page_index):
        
        # print("page_num",page_num)
        b_unit.set_description("parse page index: {}".format(page_num-content_start_page_index))
        b_unit.update(1)
        b_unit.refresh()
        page = pages[page_num]
        page_width = page.width
        page_height = page.height
        if config_is_table:
            tables = page.find_tables() # 如果没有tables就是[]
        else:
            tables = []
        # for table in tables:
        #     print("table",table,table.bbox)
        images = page.images
        if images:  
            pass
        # y_tolerance=8 可以避免中英文被分成不同行，但是可能会导致不同行文字算成同一行；
        y_tolerance=Y_TOLERANCE
        chapter = ""
        chapter_pos = (1,1,0,0)
        chapter_image_titles =[]
        chapter_table_titles=[]
        current_pagecontent=[]
        added_tables = []
        for line_num, line in enumerate(page.extract_text_lines(y_tolerance=Y_TOLERANCE)): #layout=True,
            matched = False
            prev_txt, prev_x0, prev_y0, prev_x1, prev_y1 = txt, x0, y0, x1, y1
            txt, ori_x0, ori_y0, ori_x1, ori_y1 = str(line["text"]).strip(),line["x0"],line["top"],line["x1"],line["bottom"]
            # print(">>>>",line_num,repr(txt),ori_x0, ori_y0, ori_x1, ori_y1)
            #页眉和页脚和目录,
            # print(">>>>",line_num,repr(txt),is_page_header(txt,filename))
            if is_page_footer(txt) or is_page_header(txt,filename) or ori_y1<63 :
                continue
            #去除目录部分
            if is_catalogue_line(txt) :
                # catalogue = txt[:txt.find("…")].strip()
                # # print("catalogue",catalogue)
                # if not catalogue in catalogue_lines:
                #     catalogue_lines.append(catalogue)
                continue
            
            table_index = in_table_index((ori_x0, ori_y0, ori_x1, ori_y1), tables)
            if table_index != -1:
                if table_index in added_tables:
                    continue
                added_tables.append(table_index)
                # 添加历史文件
                if len(chapter) >0:
                    current_pagecontent.append({"content":chapter,"pageno":page_num+1,"pos":chapter_pos,"type":"TXT","image_title":chapter_image_titles,"tables":chapter_table_titles})
                    chapter = ""
                    chapter_pos = (1,1,0,0)
                    chapter_image_titles =[]
                    chapter_table_titles = []
                
                # 添加表格文件 - 使用支持合并单元格的HTML格式
                table_raw_data = tables[table_index].extract()
                table_html = table_to_html_with_merge(table_raw_data)
                
                # 如果HTML转换失败，回退到原始文本格式
                if table_html:
                    table_txt = table_html
                else:
                    table_txt = str(table_raw_data).replace("None","''").replace('\\n','')
                
                pos =(tables[table_index].bbox[0]/page_width,tables[table_index].bbox[1]/page_height,tables[table_index].bbox[2]/page_width,tables[table_index].bbox[3]/page_height)
                current_pagecontent.append({"content":table_txt,"pageno":page_num+1,"pos":pos,"type":"TABLE","tables":[]})
                continue
            
            #判断是否是标题
            
            match,title_level = is_title(title_level_list,txt,catalogue_lines)
            print(txt,match,title_level)
            if match is not None:
                
                #先提交历史记录
                if len(chapter) >0:
                    current_pagecontent.append({"content":chapter,"pageno":page_num+1,"pos":chapter_pos,"type":"TXT","image_title":chapter_image_titles,"tables":chapter_table_titles})
                    chapter = ""
                    chapter_pos = (1,1,0,0)
                    chapter_image_titles =[]
                    chapter_table_titles =[]
                
                #再提交标题内容
                if type(match) == bool:
                    cur_line = txt.strip()
                else:
                    cur_line = txt.replace(" ","")
                    if cur_line=="附录":
                        cur_line = "附录"
                    elif cur_line.replace(" ","") =="参考文献":
                        cur_line ="参考文献"
                    else:
                        if config_is_replace_title_no:
                            cur_line = txt[match.end():]
                        else:
                            cur_line = txt
                
                pos =(ori_x0/page_width, ori_y0/page_height, ori_x1/page_width, ori_y1/page_height)
                current_pagecontent.append({"content":cur_line,"pageno":page_num+1,"pos":pos,"type":"TITLE","TITLE_LEVEL":title_level,"tables":[]})
                
                continue
            
            else :
                #文本文件,添加到前面去
                if len(chapter)>0 and (prev_txt[-1] == '。' or (len(prev_txt)>0 and len(prev_txt) <30)):
                    chapter += '\n' + post_split(text=txt) # 句号结尾加一个换行
                else:
                    chapter += post_split(text=txt) # 否则不换行
                chapter_pos = merge_pos(chapter_pos,(ori_x0/page_width, ori_y0/page_height, ori_x1/page_width, ori_y1/page_height)) 
                image_pattern = r"\n\b[图]\s*\d+[^，。；！？：“”‘’;、\n]*\n"
                table_pattern = r"\n\b[表]\s*\d+[^，。；！？：“”‘’;、\n]*\n"
                if re.findall(image_pattern, '\n'+txt+'\n'):
                    #拆分title，针对图片多栏情况
                    image_title_tp = split_titles(txt,ori_x0, ori_y0, ori_x1, ori_y1)
                    # image_titles = [tp[0] for tp in image_title_tp ]
                    chapter_image_titles.extend(image_title_tp)
                
                elif re.findall(table_pattern, '\n'+txt+'\n'):
                    chapter_table_titles.append(txt)
                    
    
    
        #最后，每一页内存中未提交的数据
        if len(chapter) >0:
            current_pagecontent.append({"content":chapter,"pageno":page_num+1,"pos":chapter_pos,"type":"TXT","image_title":chapter_image_titles,"tables":chapter_table_titles})
            chapter = ""
            chapter_pos = (1,1,0,0)
            chapter_image_titles =[]
            chapter_table_titles =[]
            
        #处理完当前页图的内容
        image_save_dir = str(Path(filepath).parent.parent)+"/image/"+filename
        if not os.path.exists(image_save_dir):
            os.makedirs(image_save_dir)
            
        _all_image_titlepos = []
        for content in current_pagecontent:
            if content["type"] == "TXT":
                _image_titles = content["image_title"]
                if len(_image_titles)>0:
                    _all_image_titlepos.extend(_image_titles)
        _all_image_title_txt = [t[0] for t in _all_image_titlepos]
        _all_image_title_pos = [t[1] for t in _all_image_titlepos]

        image_title_path_map={}
        
        doc = fitz.open(filepath)
        try:
            for image in images:

                image_bbox = (
                    image['x0'], 
                    page_height - image['y1'],
                    image['x1'], 
                    page_height - image['y0']
                )
                
                #异常数据
                if image_bbox[0]<=0 or image_bbox[1] <=0 or image_bbox[2] <=0 or image_bbox[3] <=0:
                    continue
                #小图
                if image_bbox[2]-image_bbox[0]<100 or image_bbox[3]-image_bbox[1]<100:
                    continue
                
                fitz_page = doc[page_num]
                page_rect = fitz_page.rect
                
                # 添加边界框验证，确保不超出页面范围
                if (image_bbox[0] >= page_rect.width or image_bbox[1] >= page_rect.height or 
                    image_bbox[2] <= 0 or image_bbox[3] <= 0):
                    print(f"警告：图像边界框 {image_bbox} 超出页面范围，跳过此图像")
                    continue
                
                # 裁剪边界框到页面范围内
                clipped_bbox = (
                    max(image_bbox[0], 0),
                    max(image_bbox[1], 0), 
                    min(image_bbox[2], page_rect.width),
                    min(image_bbox[3], page_rect.height)
                )
                
                image_name = find_image_name("",page_num,clipped_bbox,_all_image_title_txt,_all_image_title_pos,page_height)
                #没找到name
                if image_name == None:
                    continue
                image_save_path = image_save_dir+"/"+image_name+".jpg" 
                
                x0, y0, x1, y1 = clipped_bbox
                rect = fitz.Rect(x0, y0, x1, y1)
                zoom = 300 / 72.0
                mat = fitz.Matrix(zoom, zoom)
                
                pix = fitz_page.get_pixmap(matrix=mat, clip=rect)
                pix.save(image_save_path)
                
                pix = None
                
                re_image_path = str(Path(image_save_path).relative_to(Path(".").absolute()))
                image_title = image_name[image_name.find("_")+1:]
                image_title_path_map[image_title] = re_image_path
                
        finally:
            doc.close()
                # image_save_path = image_save_dir+"/"+image_name+".jpg"        
                # cropped_page = page.crop(clipped_bbox)
                # image_obj = cropped_page.to_image(resolution=72)                
                # image_obj.save(image_save_path)                
                # re_image_path = str(Path(image_save_path).relative_to(Path(".").absolute()))
                # image_title = image_name[image_name.find("_")+1:]
                # image_title_path_map[image_title]=re_image_path
            
        #更新content的内容
        for content in current_pagecontent:
            if content["type"] == "TXT":
                _image_titles = content["image_title"]
                content["images"] = [t[0] for t in _image_titles]
                content["images_path"] =[image_title_path_map.get(t,"") for t in content["images"]]
            else:
                content["images"] =[]
                content["images_path"] = []

        page_cotents.extend(current_pagecontent)

        update_progress(current_page, total_pages, kb_name, file_name)
        current_page += 1
    # for content in page_cotents:
    #     print(content)
    #     print("^^^^^^^^^^^^^^^^^^^^")
       
    return page_cotents

def title_en_stack(title_stacks,current_title):
    # 无-有
    # 高-低，没关系？
    # 低-高，同一级
    _change = False
    if len(title_stacks) == 0:
        _change = True
    while(len(title_stacks)>0):
        title_in_atack = title_stacks.pop()
        if title_in_atack["TITLE_LEVEL"]>=current_title["TITLE_LEVEL"]:
            _change = True
            pass
        else:
            title_stacks.append(title_in_atack)
            break
    title_stacks.append(current_title)
    return title_stacks,_change

def print_title_stack(title_stacks):
    return [title["content"].replace(" ","") for title in title_stacks]

def build_block(watting_block_content,title,rel_path,keywords):
    return_blocks = []
    block_content = ""
    block_postions = []
    block_image_title=[]
    block_image_path=[]
    
    for idx,content in enumerate(watting_block_content):
        block_content+=content["content"]+"\n"
        _pageno = content["pageno"]
        _pos = content["pos"]
        _images = content["images"]
        _images_path = content["images_path"]
        _tables = content["tables"]
        
        if len(block_postions) ==0 or (len(block_postions)>0 and block_postions[-1][0]!=_pageno):
            block_postion = list()
            block_postion.append(_pageno)
            block_postion.extend(_pos)
            block_postions.append(block_postion)
           
        else:
            # merge_pos
            last_pos = block_postions[-1][1:]
            block_postions[-1] =(_pageno,min(_pos[0],last_pos[0]),min(_pos[1],last_pos[1]),max(_pos[2],last_pos[2]),max(_pos[3],last_pos[3]))
            
        block_image_title.extend(_images)
        block_image_path.extend(_images_path)
        
        if len(block_content)>BLOCK_MAX_LEN or idx+1 ==len(watting_block_content):
            content_pos =[]
            for block_pos in block_postions:
                content_pos.append({"page_no":block_pos[0],
                                    'left_top': {
                                        'x': block_pos[1],
                                        'y': block_pos[2]
                                    },
                                    'right_bottom': {
                                        'x': block_pos[3],
                                        'y': block_pos[4]
                                    }
                                })
            metadata = {
                "content_pos" :content_pos,
                'images': block_image_title,
                'images_path': block_image_path,
                'tables': _tables,
                'titles': title,
                'keyword': keywords,
                'source': rel_path
            }
            #重新更新
            return_blocks.append({"content":block_content.strip(),"metadata":metadata})
            block_content = ""
            block_postions = []
            block_image_title=[]
            block_image_path=[]
            
            
    # print(title,len(return_blocks))
    
    return return_blocks

import base64
def decode_base64(s):
    decoded_string = base64.b64decode(s).decode('utf-8')
    print(repr(decoded_string))
    return decoded_string
def decode_separators(s):
    decoded_string = decode_base64(s)
    
    separators = json.loads(decoded_string)
    
    for sps in separators:
        for sp in sps:
            print(repr(sp))
    return separators


def doc_rel_path(file_path):
    if str(file_path).startswith(str(Path(".").absolute())):
        rel_path = Path(file_path).relative_to(Path(".").absolute())
        rel_path = str(rel_path.as_posix().strip("/"))
        return  rel_path
    else:
        return file_path

from server.db.repository.knowledge_file_repository import get_file_detail

class MrjOCRPDFLoader(UnstructuredFileLoader):
    def __init__(self, file_path: str or List[str], mode: str = "paged", **unstructured_kwargs: Any):
        super().__init__(file_path, mode, **unstructured_kwargs)
        self.text_splitter = ChineseChapterRecursiveSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=OVERLAP_SIZE)
        self.table_pattern = r"\n\b[表]\s*\d+[^，。；！？：“”‘’;、\n]*\n" # 提取图和表
        self.image_pattern = r"\n\b[图]\s*\d+[^，。；！？：“”‘’;、\n]*\n"
        # self.image_pattern = r"\n\b[图]\s*\d+-\d+\s+[^，。；！？：“”‘’（）《》&#8203;``【oaicite:0】``&#8203;、\n]*\n"


    
    def _get_elements(self) -> List:
        # 将pdf解析并分块
        def pdf2text(filepath):
            
            # config_path =self.file_path[:str(self.file_path).find("content")]+"file_parse_config.json"
            # print("config_path",config_path)
            
            # if os.path.exists(config_path):
            #     with open(config_path) as f:
            #         configs = json.load(f)
            #         print("configs",configs,type(configs))
            #         self.parse_file_config = configs.get(os.path.basename(filepath),None)
                    
            # else:
            #     self.parse_file_config = {}
                
            
            # print("self.parse_file_config",self.parse_file_config)

            content_index = str(self.file_path).find("content")
            if content_index == -1:
                raise ValueError("未找到 'content' 关键字")

            kb_name = os.path.basename(os.path.dirname(self.file_path[:content_index]))
            print("kb_name", kb_name)

            file_name = os.path.basename(filepath)
            print("file_name", file_name)

            file_detail = get_file_detail(kb_name=kb_name, file_name=file_name)
            self.parse_file_config = file_detail.get("file_parse_configs")
                       
            print("self.parse_file_config",self.parse_file_config)
            resp = [] 
            rel_path = doc_rel_path(filepath)
            #自定义关键字增强
            
            config_key_words = self.parse_file_config.get("key_words")
            if config_key_words is not None and len(config_key_words)>0:
                key_words = config_key_words
            else:
                key_words = [os.path.basename(filepath)[:os.path.basename(filepath).rfind(".")]]
            
            #读取当前配置文件的分割器
            config_separators = self.parse_file_config.get("separators")
            if config_separators is not None and len(config_separators)>0:
                title_level_list = decode_separators(config_separators)
                title_level_list.reverse()
                print("title_level_list",title_level_list,type(title_level_list))
                
            else:
                title_level_list = self.text_splitter.get_seperators()
                
            catalogue_lines = []
            contents = parse_pdf_content(filepath,title_level_list,catalogue_lines,self.parse_file_config)
            watting_build_content = []
           
            title_stacks = []
            for content in contents:
                _type = content["type"]  
                if _type == "TITLE":
                    title_stacks_temp,change = title_en_stack(title_stacks.copy(),content)
                    if len(watting_build_content)>0:
                        #把上一章节提交了
                        _title = print_title_stack(title_stacks)
                        
                        blocks = build_block(watting_build_content,_title,rel_path,key_words)
                        watting_build_content =[]
                        
                        for block in blocks:
                            doc = create_documents(chapter=block["content"], 
                                                    title_stack=_title, 
                                                    title_prefix=self.text_splitter.title_prefix,
                                                    metadata=block["metadata"])
                            resp.extend(doc)
                        
                    #标题处理，平行级别，低级别到高级别，高到低
                    title_stacks = title_stacks_temp

                    pass
                elif _type== "TXT" or _type== "IMAGE" or  _type== "TABLE":
                    watting_build_content.append(content)
                else:
                    print("error ",content)
                    pass
                
                
            if len(watting_build_content)>0:
                _title = print_title_stack(title_stacks)
                
                blocks = build_block(watting_build_content,_title,rel_path,key_words)
                watting_build_content =[]
                for block in blocks:
                    doc = create_documents(chapter=block["content"], 
                                            title_stack=_title, 
                                            title_prefix=self.text_splitter.title_prefix,
                                            metadata=block["metadata"])
                    resp.extend(doc)    
            return resp
        
        
        
        if self.file_path[-5:] == ".docx":
            from server.knowledge_base.word2pdf import doc2pdf
            doc2pdf(self.file_path)
            self.file_path = self.file_path[:-5] + ".pdf"
            
        text = pdf2text(self.file_path)
        if GENERATE_OUTPUT_JSON:
            new_next = []
            filename = str(os.path.basename(self.file_path))
            last_dot_index = filename.rfind(".")
            filename = filename[:last_dot_index] 
            
            query_context_answer_source = []
            
            for idx,sub_text in enumerate(text):
                new_next.append([len(sub_text.page_content), sub_text.metadata, sub_text.page_content])
                query= sub_text.metadata['titles']
                # query =query[str(query).rfind("#")+1:]
                
                #根据章节生成问题
                if len(sub_text.page_content)>50 and self.parse_file_config.get("generate_query","False") == "True":
                    generate_questions = gen_question(query+"\n"+sub_text.page_content)
                    generate_questions = "\n".join(generate_questions)
                else:
                    generate_questions=""
                query_context_answer_source.append([query,sub_text.page_content,sub_text.metadata['images'],generate_questions])
                sub_text.metadata['g_query']=generate_questions

                # print(str(idx)+"/"+str(len(text)),query,sub_text.page_content,"\n"+generate_questions)
                # print("===="*5)
                
            # with open("document_loaders/"+filename+".json", 'w') as f:
            #     json.dump(new_next, f, ensure_ascii=False, indent=4)
            # csv_save_dir = str(Path(self.file_path).parent.parent)+"/csv/"
            # if not os.path.exists(csv_save_dir):
            #     os.makedirs(csv_save_dir)
            # print("csv_save_dir:",csv_save_dir)
            # import csv
            # with open(csv_save_dir+filename+".csv", 'w', newline='') as f:
            #     writer = csv.writer(f)
            #     writer.writerows(query_context_answer_source)
                
        return text

    def load(self) -> List[Document]:
        docs = self._get_elements()
        return docs



    def pre_get_elements(self) -> List:
        def pdf2text(filepath):
            import fitz
            doc = fitz.open(filepath)
            b_unit = tqdm.tqdm(total=doc.page_count, desc="MrjOCRPDFLoader context page index: 0")
            resp = []
            for i in range(len(doc)):
                b_unit.set_description("MrjOCRPDFLoader context page index: {}".format(i))
                b_unit.refresh()
                page = doc.load_page(i)
                page_text = page.get_text()
                resp.append(remove_special_chars(text=page_text)) 
                b_unit.update(1)
            return resp
        text = pdf2text(self.file_path)
        for chapter in text:
            chapter.metadata['source'] = self.file_path
        return text

class RapidOCRPDFLoader(UnstructuredFileLoader):
    def _get_elements(self) -> List:
        def pdf2text(filepath):
            import fitz # pyMuPDF里面的fitz包，不要与pip install fitz混淆
            from rapidocr_onnxruntime import RapidOCR
            import numpy as np
            ocr = RapidOCR()
            doc = fitz.open(filepath)
            resp = ""

            b_unit = tqdm.tqdm(total=doc.page_count, desc="RapidOCRPDFLoader context page index: 0")
            for i, page in enumerate(doc):

                # 更新描述
                b_unit.set_description("RapidOCRPDFLoader context page index: {}".format(i))
                # 立即显示进度条更新结果
                b_unit.refresh()
                # TODO: 依据文本与图片顺序调整处理方式
                text = page.get_text("")
                resp += text + "\n"

                img_list = page.get_images()
                for img in img_list:
                    pix = fitz.Pixmap(doc, img[0])
                    img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, -1)
                    result, _ = ocr(img_array)
                    if result:
                        ocr_result = [line[1] for line in result]
                        resp += "\n".join(ocr_result)

                # 更新进度
                b_unit.update(1)
            return resp

        text = pdf2text(self.file_path)
        from unstructured.partition.text import partition_text
        return partition_text(text=text, **self.unstructured_kwargs)


if __name__ == "__main__":
    project_path =Path(".").absolute()
    # path = str(project_path)+"/"+"knowledge_base/lb_test/content/陕汽-重卡X5000维修手册（第一部分）.pdf"
    
    # content_start_page_index = 14
    # Y_TOLERANCE = 2
    # PAGE_HEAD_LIST =["一学就会的500项汽车维修技能第2版"]
    # path = "/mnt/ddata/datasets/cc_data/ebook/汽车维修/一学就会的500项汽车维修技能_第2版.pdf"
    
    # content_start_page_index = 0
    # Y_TOLERANCE = 2
    # PAGE_HEAD_LIST =["一学就会的500项汽车维修技能第2版"]
    # path = "/mnt/ddata/datasets/cc_data/ebook/汽车维修/汽车修理技师手册_第3版.pdf"
    
    
    # content_start_page_index = 39
    # Y_TOLERANCE = 3
    # PAGE_HEAD_LIST =["最新汽车维修1128问"]
    # path = "/mnt/ddata/datasets/cc_data/ebook/汽车维修/最新汽车维修1128问.pdf"
    
    # content_start_page_index = 4
    # Y_TOLERANCE = 3
    # PAGE_HEAD_LIST =["汽车典型故障快修200例（全彩版）"]
    # path = "/mnt/ddata/datasets/cc_data/ebook/汽车维修/汽车典型故障快修200例（全彩版）.pdf"
    
    
    # content_start_page_index = 25
    # Y_TOLERANCE = 3
    # # "AP1000核电厂概述","反应堆系统","AP1000反应堆冷却剂系统","非能动堆芯冷却系统","安全壳和安全壳系统","辅助系统","蒸汽动力转换系统","电气系统","仪表控制系统","AP1000安全分析"
    # PAGE_HEAD_LIST =["非能动安全先进核电厂AP1000",]
    # path = "/home/star/projects/chat_doc/knowledge_base/test_nuclear/content/非能动安全先进核电厂AP1000.pdf"
    
    
    
    # [
    #     [r'\b\([一二三四五六七八九十]{1,2}\)',r'\b[一二三四五六七八九十]{1,2}[、.]',],
    #     [r'\b^\d+\.\d+\.\d+\.\d+\.\d+\s'],                                                #1.1.1.1.1
    #     [r'\b^\d+\.\d+\.\d+\.\d+\s'],                                                     #1.1.1.1
    #     [r'\b^\d+\.\d+\.\d+\s'],                                                          #1.1.1
    #     [r'\b^\d+\.\d+\s'],                                                               #1.1
    #     [r'\b^\d+\s'],   #[r'\b^xxxxxxx'],      # 占位             [r'\b^\d+(?:\s+|、\s*)']  r'\b^\d+(?:\.\s+|、\s*)'                                       #1. 
    #     [r'\b^第\s*(?:[一二三四五六七八九十]{1,2}|\d+)\s*[节]',r'\b^附\s*录\s*[A-Z]'], 
    #     [r'\b^第\s*(?:[一二三四五六七八九十]{1,2}|\d+)\s*[章]',r'\b^附\s*录',r'\b^参\s*考\s*文\s*献',r'\b^附表\s+'], 
    # ]
    
    
    # content_start_page_index = 19
    # Y_TOLERANCE = 2
    # # "AP1000核电厂概述","反应堆系统","AP1000反应堆冷却剂系统","非能动堆芯冷却系统","安全壳和安全壳系统","辅助系统","蒸汽动力转换系统","电气系统","仪表控制系统","AP1000安全分析"
    # PAGE_HEAD_LIST =["中国自主先进压水堆技术“华龙一号”",]
    # path = "/home/star/projects/chat_doc/knowledge_base/test_nuclear/content/中国自主先进压水堆技术“华龙一号”(上册).pdf"

    
    # content_start_page_index = 0
    # Y_TOLERANCE = 9
    # PAGE_HEAD_LIST =["核电厂设计安全规定"]
    # path = "/home/star/projects/chat_doc/knowledge_base/nuclear_law/content/核出口管制清单.pdf"
    
    
    # content_start_page_index = 0
    # Y_TOLERANCE = 3
    # PAGE_HEAD_LIST =["核电厂设计安全规定"]
    # path = "/home/star/projects/chat_doc/knowledge_base/nuclear_law/content/核电厂设计安全规定.pdf"
    
    
    content_start_page_index = 0
    Y_TOLERANCE = 3
    PAGE_HEAD_LIST =["核电厂设计安全规定"]
    # path = "/home/star/projects/chat_doc/knowledge_base/nuclear_law/content/核动力厂反应堆安全壳 及其有关系统的设计.pdf"
    path = "/mnt/ddata/datasets/cc_data/ebook/核电/非能动安全先进核电厂AP1000.pdf"
    
    
    # content_start_page_index = 0
    # Y_TOLERANCE = 6
    # PAGE_HEAD_LIST =["核电厂设计安全规定"]
    # path = "/home/star/projects/chat_doc/knowledge_base/nuclear_law/content/GB 50745-2012 核电厂常规岛厂设计防火规范.pdf"
    
    
    # content_start_page_index = 0
    # Y_TOLERANCE = 6
    # PAGE_HEAD_LIST =["核动力厂防火与防爆设计"]
    # path = "/home/star/projects/chat_doc/knowledge_base/nuclear_law/content/HAD 102:11–2019 核动力厂防火与防爆设计.pdf"
    
    
    GENERATE_OUTPUT_JSON = True
    # SAVE_IMAGE = False
    loader = MrjOCRPDFLoader(file_path=path)
    docs = loader.load()
    # print(docs)
    # str_1 = "123"
    # list_1 =[1,2,4]
    # d={"s":str_1,"l":list_1}
    # print(d)
    # str_1 =''
    # list_1 =[]
    # print(d)
    
    
    # text_splitter = ChineseChapterRecursiveSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=OVERLAP_SIZE)
    # text = "①变速器内轴承（一、二轴轴承，差速器轴承）磨损；②齿轮（一、二轴传动齿轮，差速"
    # result = is_title(text_splitter.get_seperators(),text,[])
    # print(result)
    
    # pages = pdfplumber.open(path).pages
    # for page_num in range(len(pages)):
    #     page = pages[page_num]
    #     # tables = page.find_tables()
    #     # for table in tables:
    #     #     print(table.extract())
    #     #     print("_________________")
    #     print(page.extract_text())
    # from pdfminer.high_level import extract_text
    # text = extract_text(path)
    
    
    
    # txt_list =["第二章 反应堆系统","第二章 反应堆系统 13","第二章 反应堆系统13","附 录13","附 录A","附 录A 12"]
    # repr_str_list= [r'\b^第\s*(?:[一二三四五六七八九十]{1,2}|\d+)\s*[章]\s*\S*\s*\d',r'\b^附 录\S*\s*\d',r'\b^参 考 文 献\S*\s*\d']
    
    # txt_list =[
    #     "序 论......................................................................................................(1)",
    #     "0.1 核电发展历史 ............................................................................................(1)",
    #     "第二章 反应堆系统13.........(1)",
    #     "第 一 章 AP1000 核电厂概述 ................................................................... (16)",
    #     "第 一 章 AP1000 核电厂概述 ................................................................... 16",
    #     "第 一 章 AP1000 核电厂概述 ...................................................................16",
    #     "...................................................................",
    #     "第 一 章 AP1000 核电厂概述 ……16",
    #     "第 一 章 AP1000 核电厂概述 …16",
    #     "第 一 章 AP1000 核电厂概述 ..................................................................."
    #     ]
    
    # repr_str_list=[r'^.*\…{2,}.*\d$',r'^.*\.{6,}\s*\(*\d\)*']   #r'\S+(\.){6,}\s*(\()*\d(\))*$'
    # for txt in txt_list:
    #     for repr_str in repr_str_list:
    #         print(txt,re.match(repr_str,txt))
    #     print("---------")



# # txt ="4｜中国自主先进压水堆技术“华龙一号”"
# txt ="4｜中国自主先进压水 堆技术“华龙一号”"
# # result = is_page_header(txt,"中国自主先进压水堆技术“华龙一号"")
# # result = re.match('\b^\d\s+',txt)
# result = re.match('^\d(\s*|｜)\S+',txt)
# print(result)

# txt2 ="中国自主先进压水堆技术“华龙一号”｜4"
# txt2 ='第章绪论｜3'
# result2 = re.match('\S+.(\s*|｜)\d$',txt2)
# print(result2)
# context ="116. 汽车由哪几部分组成？\n汽车通常由发动机、 底盘、 车身和电气设备四大部分组成。\n1） 发动机是汽车的动力装置， 其作用是将燃料燃烧所产生的热能转变为机械能输出。大多数汽车发动机都采用往复活塞式内燃机， 所用的燃料以汽油和柴油为主。 汽油发动机一般是由机体组、 曲柄连杆机构、配气机构、 燃料供给系统、 润滑系统、 冷却系统、 点火系统、 起动系统、 电控系统等部分组成。 以柴油为燃料的发动机， 采用压燃式， 无点火系统。\n2） 底盘是汽车装配与行驶的主体， 其作用是支撑、 安装发动机和车身等其他总成与部件， 形成汽车的整体造型， 并接受发动机输出的动力， 使汽车能够运动， 保证汽车正常行驶。 底盘由传动系统、 行驶系统、 转向系统和制动系统四大部分组成。\n① 传动系统的作用是通过各种传动装置把发动机的动力传给各驱动车轮。 传动系统由离合器、 变速器、 传动轴和驱动桥等组成。\n② 行驶系统的作用是把汽车各总成及部件连成一个整体， 并对全车起支撑作用， 以保证汽车正常行驶。 行驶系统由车架、 前桥、 驱动桥的壳体、 车轮、 悬架等组成。\n③ 转向系统的作用是保证汽车能按照驾驶人选择的方向行驶， 由带转向盘的转向器及转向传动装置组成。\n④ 制动系统的作用是控制汽车， 使汽车减速或停车， 并保证驾驶人离去后汽车能可靠停驻。 每辆汽车的制动装置都包括若干个相互独立的制动系统， 每个制动系统都由供能装置、 控制装置、 传动装置和制动器组成。\n3） 车身是驾驶人工作的场所， 也是装载乘客和货物的场所。 车身为驾驶人提供方便的操作条件， 并为乘客提供舒适安全的环境或保证货物完好无损。 轿车、 客车的车身一般是整体结构， 货车车身一般由驾驶室和货厢两部分组成。\n4） 电气设备由电源组、 发动机起动系统和点火系统、 汽车照明和信号装置等组成。 此外， 在现代汽车上越来越多地装用各种电子设备， 如微处理机、 中央计算机系统及各种人工智能装置 （防抱死系统、 安全气囊、 定速巡航、 定位系统等）， 显著地提高了汽车的安全性能。"
# response = gen_question(context)
# print(response)


# import PyPDF2
# with open("","rb") as pdf_file:
#     pdf_reader = PyPDF2.PdfFileReader(pdf_file)
#     outlines = pdf_reader.getOutlines()
#     for outline in outlines:
#         print("outline",outline)



#相似度



    
    









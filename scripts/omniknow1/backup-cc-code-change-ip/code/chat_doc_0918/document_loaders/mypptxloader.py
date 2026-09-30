# created by XuJJ

import re
from pptx import Presentation
import os
from pathlib import Path
import requests
from langchain.docstore.document import Document
from langchain.document_loaders.unstructured import UnstructuredFileLoader
from typing import Dict, List, Optional, Any
from server.knowledge_base.pptx2pdf import pptx2pdf
import subprocess
import shutil

class NuclearPPTLoader(UnstructuredFileLoader):
    def __init__(self, file_path: str or List[str], extract_image: bool = True, **kwargs):
        """
        初始化加载器，指定文件路径和是否提取图片
        """
        # 检查文件扩展名，如果是.ppt则转换为.pptx
        original_file_path = file_path
        if file_path.lower().endswith('.ppt'):
            file_path = self._convert_ppt_to_pptx(file_path)
            
        super().__init__(file_path, **kwargs)
        self.extract_image = extract_image
        self.original_file_path = original_file_path

        ppt_parent_dir = Path(file_path).parent.parent
        filename = Path(file_path).stem

        self.image_dir = os.path.join(ppt_parent_dir, "image", filename)
        if not os.path.exists(self.image_dir):
            try:
                os.makedirs(self.image_dir, exist_ok=True)
            except PermissionError as e:
                raise PermissionError(f"Cannot create directory {self.image_dir}. Please check write permissions.") from e

        self.pdf_path = str(Path(file_path).with_suffix('.pdf'))
        
        # 生成ppt文件
        self.pdf = pptx2pdf(file_path)

    def _convert_ppt_to_pptx(self, ppt_file_path: str) -> str:
        """
        将.ppt文件转换为.pptx文件
        """
        pptx_file_path = ppt_file_path.replace('.ppt', '.pptx')
        
        # 如果.pptx文件已存在，直接返回
        if os.path.exists(pptx_file_path):
            print(f"PPTX文件已存在: {pptx_file_path}")
            return pptx_file_path
            
        try:
            # 使用LibreOffice转换.ppt到.pptx
            print(f"正在转换 {ppt_file_path} 为 {pptx_file_path}...")
            
            # 构建LibreOffice命令
            output_dir = os.path.dirname(pptx_file_path)
            cmd = [
                'libreoffice',
                '--headless',
                '--convert-to', 'pptx',
                '--outdir', output_dir,
                ppt_file_path
            ]
            
            # 执行转换命令
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            if result.returncode == 0:
                # 检查转换后的文件是否存在
                if os.path.exists(pptx_file_path):
                    print(f"成功转换为: {pptx_file_path}")
                    return pptx_file_path
                else:
                    raise Exception(f"转换完成但找不到输出文件: {pptx_file_path}")
            else:
                raise Exception(f"LibreOffice转换失败: {result.stderr}")
                
        except subprocess.TimeoutExpired:
            raise Exception(f"转换超时: {ppt_file_path}")
        except FileNotFoundError:
            raise Exception("未找到LibreOffice，请确保已安装LibreOffice")
        except Exception as e:
            print(f"转换失败: {e}")
            # 如果转换失败，返回原文件路径，让后续处理决定如何处理
            raise Exception(f"无法转换PPT文件 {ppt_file_path}: {str(e)}")

    def load(self) -> List[Document]:
        """
        加载PPT文件并解析为Document对象列表
        """
        docs = []
        try:
            ppt = Presentation(self.file_path)
        except KeyError as e:
            if "no relationship of type" in str(e):
                print(f"Warning: PPT文件 {self.file_path} 格式不支持或已损坏")
                # 如果是转换后的文件仍然有问题，尝试使用原始文件路径信息
                error_doc = Document(
                    page_content=f"PPT文件加载失败: {os.path.basename(self.original_file_path)}。文件可能已损坏或格式不支持。",
                    metadata={
                        "content_pos": [{"page_no": 1, "left_top": {"x": 0, "y": 0}, "right_bottom": {"x": 540, "y": 720}}],
                        "images": [],
                        "images_path": [],
                        "tables": [],
                        "titles": "",
                        "keyword": [],
                        "source": self.pdf_path,
                        "error": "PPT格式不支持"
                    }
                )
                return [error_doc]
            else:
                raise e
        except Exception as e:
            print(f"Error: 加载PPT文件 {self.file_path} 时出现未知错误: {e}")
            error_doc = Document(
                page_content=f"PPT文件加载失败: {os.path.basename(self.original_file_path)}。错误: {str(e)}",
                metadata={
                    "content_pos": [{"page_no": 1, "left_top": {"x": 0, "y": 0}, "right_bottom": {"x": 540, "y": 720}}],
                    "images": [],
                    "images_path": [],
                    "tables": [],
                    "titles": "",
                    "keyword": [],
                    "source": self.pdf_path,
                    "error": str(e)
                }
            )
            return [error_doc]

        image_counter = 0
        for slide_number, slide in enumerate(ppt.slides):
            page_content, metadata = self._parse_slide(slide, slide_number, image_counter)
            docs.append(Document(page_content=page_content, metadata=metadata))
            image_counter = metadata.get("next_image_counter", image_counter)

        print(docs)
        return docs

    def _parse_slide(self, slide, slide_number: int, image_counter: int) -> (str, dict):
        """
        解析单个幻灯片，提取文本内容和图片+图形文本+连接符文本+SmartArt文本
        """

        text_content = []
        auto_shapes = []   
        connectors = []    
        smart_arts = []    
        image_paths = []
        image_names = []
        image_descriptions = []

        for shape in slide.shapes:
            # 首先提取图片（如果需要）
            if self.extract_image:
                extracted_images, descriptions, image_counter = self._extract_image_from_shape(
                    shape, self.image_dir, image_counter, slide_number
                )
                for img_path, img_name in extracted_images:
                    # 检查是否已存在相同路径的图片
                    if img_path not in image_paths:
                        image_paths.append(img_path)
                        image_names.append(img_name)
                # 只添加对应新图片的描述
                new_descriptions = []
                for i, (img_path, _) in enumerate(extracted_images):
                    if img_path in image_paths and i < len(descriptions):
                        # 确保描述与图片一一对应且不重复
                        if len(image_descriptions) < len(image_paths):
                            new_descriptions.append(descriptions[i])
                image_descriptions.extend(new_descriptions)
            
            # 然后处理文本内容
            if shape.shape_type == 1: 
                if shape.has_text_frame and (text := shape.text_frame.text.strip()):
                    auto_shapes.append(text)
                    text_content.append(f"{text}")
                    continue
                    
            elif shape.shape_type == 25: 
                if shape.has_text_frame and (text := shape.text_frame.text.strip()):
                    connectors.append(text)
                    text_content.append(f"{text}")
                    continue
                    
            elif shape.shape_type == 6:  # GroupShape
                # 只处理文本，图片已经在上面的_extract_image_from_shape中处理过了
                def process_group_text_only(g_shape):
                    for sub_shape in g_shape.shapes:
                        if sub_shape.has_text_frame and (text := sub_shape.text_frame.text.strip()):
                            smart_arts.append(text)
                            text_content.append(f"{text}")
                        if sub_shape.shape_type == 6:
                            process_group_text_only(sub_shape)
                process_group_text_only(shape)
                continue

            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    paragraph_text = ''.join(run.text for run in paragraph.runs)
                    # paragraph_text = self._clean_paragraph(paragraph_text)
                    if paragraph_text.strip():
                        text_content.append(paragraph_text)
            
            # 提取表格
            if shape.has_table:
                table_html = ['<table>']
                for row in shape.table.rows:
                    table_html.append('<tr>')
                    for cell in row.cells:
                        table_html.append(f'<td>{cell.text.strip()}</td>')
                    table_html.append('</tr>')
                table_html.append('</table>')
                text_content.append(''.join(table_html))

        # 页面内容
        page_content = '.'.join(text_content)
        if image_descriptions:
            page_content += '/Images: '.join(image_descriptions)+ '; '
            
        metadata = {
            "content_pos":[{"page_no": slide_number + 1,"left_top": {"x": 0,"y": 0},"right_bottom": {"x": 540,"y": 720}}],
            "images": image_names,
            "images_path": image_paths,
            "tables": [],
            "titles": "",
            "keyword": [],
            "source": self.pdf_path,
            "next_image_counter": image_counter
        }

        return page_content, metadata

    def _extract_image_from_shape(self, obj, path, counter, slide_number):
        """
        提取图片并返回其路径和描述
        """
        image_data = []
        descriptions = []
        if hasattr(obj, "image"):
            try:
                imdata = obj.image.blob
                imagetype = obj.image.content_type
                imtype = imagetype.split("/")[-1]

                temp_image_file = os.path.join(path, f"temp_picture_{counter}.{imtype}")
                with open(temp_image_file, 'wb') as file_str:
                    file_str.write(imdata)

                # 调用描述服务
                try:
                    description = self._describe_image_via_service(temp_image_file)
                    sanitized_description = re.sub(r'[\\/*?:"<>|]', '_', description)
                except Exception as e:
                    print(f"Error describing image: {e}")
                    sanitized_description = "undesc"

                image_name = f"{slide_number + 1}_{sanitized_description}"  # 使用页码和计数器生成名称
                final_image_file = os.path.join(path, f"{image_name}.{imtype}")

                os.rename(temp_image_file, final_image_file)
                print(f"Extracted and renamed: {final_image_file}")
                image_data.append((final_image_file, image_name))
                descriptions.append(sanitized_description)
                counter += 1

            except Exception as e:
                print(f"Error extracting image: {e}")
        elif obj.shape_type == 6:  # GroupShape
            for sub_shape in obj.shapes:
                sub_image_data, sub_descriptions, counter = self._extract_image_from_shape(
                    sub_shape, path, counter, slide_number
                )
                image_data.extend(sub_image_data)
                descriptions.extend(sub_descriptions)  # 修复：合并子形状的描述

        return image_data, descriptions, counter

    def _clean_paragraph(self, text):
        """
        清理文本内容
        """
        text = re.sub(r'\(cid:\d+\)', '', text)
        text = re.sub(r'[0-9A-Fa-f]{21,}', '', text)
        text = re.sub(r'[.\- —。_*]{7,}', '\t', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text

    def _describe_image_via_service(self, image_path):
        """
        调用HTTP服务描述图片。
        服务地址走环境变量 IMG_DESC_PPTX_URL（/deploy/deploy.env）；
        未配置=服务未部署，跳过描述（返回 "undesc"，走解析降级路径）。
        """
        import os
        service_url = os.getenv("IMG_DESC_PPTX_URL", "")
        if not service_url:
            return "undesc"
        payload = {"image_path": image_path}

        try:
            response = requests.post(service_url, json=payload, timeout=10)  # 添加超时
            if response.status_code == 200:
                return response.json().get("description", "No description")
            else:
                print(f"Error from service: {response.status_code}, {response.text}")
                return "undesc"
        except requests.RequestException as e:
            print(f"Error calling describe_image service: {e}")
            return "undesc"


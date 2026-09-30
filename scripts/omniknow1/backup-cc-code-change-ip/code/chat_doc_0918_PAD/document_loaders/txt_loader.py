import sys
sys.path.append("./")
from typing import Any, List, Union, Dict, Optional
from langchain.document_loaders.unstructured import UnstructuredFileLoader
import re
import os
from pathlib import Path
from langchain.docstore.document import Document
from copy import deepcopy
import chardet

DEFAULT_TITLE_PATTERNS = [
    # 一级标题
    [
        r'^第\s*(?:[一二三四五六七八九十]+|[0-9]+)\s*[章]\s*',  # 第一章
        r'^标题\s*\d+',  # 标题1
        r'^\w\s*规范\s*文\s*件',  # X规范文件
        r'^标题表\s*',  # 标题表
        r'^第\s*[一二三四五六七八九十]+\s*[章节篇]\s*[：:]\s*(.+)$',  # 第一章：标题
        r'^第\s*\d+\s*[章节篇]\s*[：:]\s*(.+)$',  # 第1章：标题
    ],
    
    # 二级标题
    [
        r'^第\s*(?:[一二三四五六七八九十]+|[0-9]+)\s*[节]\s*',  # 第一节
        r'^标题\s*\d+\s*[A-Z]',  # 标题1A
        r'^[一二三四五六七八九十]+[、.]\s*(.+)$',  # 一、标题
        r'^\d+[、.]\s*(.+)$',  # 1、标题
        r'^[（(][一二三四五六七八九十]+[)）]\s*(.+)$',  # (一)标题
        r'^[（(]\d+[)）]\s*(.+)$',  # (1)标题
    ],
    
    # 三级标题
    [
        r'^\d+\s',  # 1 
        r'^[a-zA-Z][、.]\s*(.+)$',  # a. 标题
    ],
    
    # 四级标题
    [
        r'^\d+(\.\d+){1}\s',  # 1.1 
    ],
    
    # 五级标题
    [
        r'^\d+(\.\d+){2}\s',  # 1.1.1 
    ],
    
    # 六级标题
    [
        r'^\d+(\.\d+){3}\s',  # 1.1.1.1 
    ],
    
    # 七级标题
    [
        r'^\d+(\.\d+){4}\s',  # 1.1.1.1.1 
    ]
]

DEFAULT_KEYWORD_DICT = {
    "维修": "维修",
    "故障": "故障",
    "参数": "参数",
    "属性": "属性",
    "操作": "操作",
    "使用": "使用",
    "步骤": "步骤",
    "安装": "安装",
    "配置": "配置",
    "设置": "设置",
    "注意": "注意",
    "警告": "警告",
    "危险": "危险",
    "提示": "提示",
    "说明": "说明",
    "介绍": "介绍",
    "概述": "概述",
    "总结": "总结",
    "方法": "方法",
    "技术": "技术",
    "规格": "规格",
    "标准": "标准",
    "要求": "要求",
    "流程": "流程",
    "原理": "原理",
    "功能": "功能",
    "特性": "特性",
    "结构": "结构",
    "组成": "组成",
    "分类": "分类",
    "类型": "类型"
}

def find_codec(blob):
    """
    检测文件编码
    """
    detected = chardet.detect(blob[:1024])
    if detected['confidence'] > 0.5:
        return detected['encoding']
    
    common_encodings = ['utf-8', 'gb2312', 'gbk', 'utf-16', 'ascii', 'big5']
    for encoding in common_encodings:
        try:
            blob[:1024].decode(encoding)
            return encoding
        except Exception:
            pass
    
    return "utf-8"

def remove_special_chars(text: str) -> str:
    """
    移除特殊字符
    """
    special_chars = r"[-.]{2,}|[■…]"
    text = re.sub(special_chars, "", text)
    return text

def post_process_text(text: str) -> str:
    """
    处理文本，移除多余的空格和换行
    """
    text = remove_special_chars(text)
    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r' ?\n ?', '\n', text)
    text = re.sub(r'\n{2,}', '\n', text)
    
    pattern = re.compile(r'(?<=[^\W\d])\s+(?=[^\W\d])')
    text = pattern.sub('', text).strip()
    
    return text

def is_title(line: str, title_patterns: List[List[str]]) -> (bool, int):
    """
    判断一行文本是否为标题，并返回标题级别
    """
    for level, patterns in enumerate(title_patterns):
        for pattern in patterns:
            match = re.search(pattern=pattern, string=line)
            if match:
                return True, level
    return False, -1

def create_documents(chapter: str, title_stack: List[str], title_prefix: str, metadata: Dict) -> List[Document]:
    """
    根据章节内容和标题创建文档
    """
    prefix = ""
    for i, sub_title in enumerate(title_stack):
        if sub_title:
            prefix += title_prefix * i + sub_title
    
    prefix = re.sub(r'\s+', '', prefix)
    metadata['titles'] = prefix
    metadata['keyword'] = []
    
    # 处理文本，但不包含标题行
    chapter = post_process_text(text=chapter)
    
    # 提取关键词
    for key, value in DEFAULT_KEYWORD_DICT.items():
        if re.findall(key, chapter):
            metadata['keyword'].append(value)
    
    docs = [Document(page_content=chapter, metadata=deepcopy(metadata))]
    return docs

class TxtLoader(UnstructuredFileLoader):
    """
    TXT文件加载器，支持按标题分块
    """
    def __init__(
        self, 
        file_path: str or List[str], 
        title_patterns: List[List[str]] = None,
        keyword_dict: Dict[str, str] = None,
        title_prefix: str = "##",
        **kwargs
    ):
        """
        初始化TXT加载器
        
        Args:
            file_path: TXT文件路径
            title_patterns: 标题匹配的正则表达式列表，按层级组织
            keyword_dict: 关键词字典，用于提取文档中的关键信息
            title_prefix: 标题前缀，用于构建标题层级
            **kwargs: 其他参数
        """
        super().__init__(file_path, **kwargs)
        self.file_path = file_path
        self.title_patterns = title_patterns or DEFAULT_TITLE_PATTERNS
        self.keyword_dict = keyword_dict or DEFAULT_KEYWORD_DICT
        self.title_prefix = title_prefix
    
    def load(self) -> List[Document]:
        """
        加载TXT文件并解析为Document对象列表
        """
        docs = []
        
        with open(self.file_path, 'rb') as f:
            file_content = f.read()
        
        encoding = find_codec(file_content)
        text = file_content.decode(encoding, errors='ignore')
        
        lines = text.split('\n')
        
        current_chapter = ""
        title_stack = [""] * len(self.title_patterns)
        current_level = -1
        
        metadata = {
            "source": self.file_path,
            "content_pos": [{"page_no": 1, "left_top": {"x": 0, "y": 0}, "right_bottom": {"x": 0, "y": 0}}],
            "images": [],
            "images_path": [],
            "tables": [],
            "titles": "",
            "keyword": []
        }
        
        for line_idx, line in enumerate(lines):
            line = line.strip()
            if not line:
                current_chapter += "\n"
                continue
            
            is_title_line, title_level = is_title(line, self.title_patterns)
            
            if is_title_line:
                # 如果当前有内容，创建文档
                if current_chapter.strip():
                    new_docs = create_documents(
                        current_chapter, 
                        title_stack, 
                        self.title_prefix, 
                        deepcopy(metadata)
                    )
                    docs.extend(new_docs)
                    current_chapter = ""
                
                # 更新标题栈
                title_stack[title_level] = line
                # 清空更低级别的标题
                for i in range(title_level + 1, len(title_stack)):
                    title_stack[i] = ""
                
                current_level = title_level

            else:
                current_chapter += line + "\n"
        
        # 处理最后一个章节
        if current_chapter.strip():
            new_docs = create_documents(
                current_chapter, 
                title_stack, 
                self.title_prefix, 
                deepcopy(metadata)
            )
            docs.extend(new_docs)
        
        return docs

if __name__ == "__main__":
    """
    使用示例
    """
    # 自定义标题模式
    custom_title_patterns = [
        [r'^第\s*[一二三四五六七八九十]+\s*[章节]\s*(.+)$', r'^第\s*\d+\s*[章节]\s*(.+)$'],  # 一级标题
        [r'^[一二三四五六七八九十]+[、.]\s*(.+)$', r'^\d+[、.]\s*(.+)$'],  # 二级标题
    ]
    
    # 加载TXT文件
    loader = TxtLoader(
        file_path="./example.txt",
        title_patterns=custom_title_patterns
    )
    
    # 获取文档列表
    docs = loader.load()
    print(f"共加载了 {len(docs)} 个文档块")
    
    # 打印文档内容
    for i, doc in enumerate(docs):
        print(f"文档 {i+1}:")
        print(f"标题: {doc.metadata['titles']}")
        print(f"关键词: {doc.metadata['keyword']}")
        print(f"内容: {doc.page_content[:100]}...")
        print("-" * 50)
import re
from typing import List, Optional, Any
from langchain.text_splitter import RecursiveCharacterTextSplitter
import logging
from langchain.docstore.document import Document
logger = logging.getLogger(__name__)
Default_CATE_REPS = [
                [r'\b\([一二三四五六七八九十]{1,2}\)',r'\b[一二三四五六七八九十]{1,2}[、.]',],
                # [r'\b^\d+\.\d+\.\d+\.\d+\.\d+\s'],                                                #1.1.1.1.1
                # [r'\b^\d+\.\d+\.\d+\.\d+\s'],                                                     #1.1.1.1
                # [r'\b^\d+\.\d+\.\d+\s'],                                                          #1.1.1
                [r'\b^\d+\.\d+\s'],                                                               #1.1
                [r'\b^\d+\s'],   #[r'\b^xxxxxxx'],      # 占位             [r'\b^\d+(?:\s+|、\s*)']  r'\b^\d+(?:\.\s+|、\s*)'                                       #1. 
                [r'\b^第\s*(?:[一二三四五六七八九十]{1,2}|\d+)\s*[节]',r'\b^附\s*录\s*[A-Z]'], 
                [r'\b^第\s*(?:[一二三四五六七八九十]{1,2}|\d+)\s*[章]',r'\b^附\s*录',r'\b^参\s*考\s*文\s*献',r'\b^附表\s+'], 
                ]

def is_regex(s):
    special_chars = re.compile(r'[\.\*\+\?\|\(\)\[\]\{\}]')
    return bool(special_chars.search(s))

def potential_title(s: str) -> str:
    """
    找到一段string中潜在标题
    由于是按照标题分段，因此第一个换行以前可以认为是潜在标题
    """
    if len(s) == 0:
        return False
    index_of_newline = s.find('\n')
    if index_of_newline == -1:
        return re.sub(r'\s+', '', s)
    return re.sub(r'\s+', '', s[:index_of_newline])

def get_sub_paragraph(prefix: str, 
                      titles_before: str, 
                      paragraph: str, 
                      patterns: List[str], 
                      index: int, 
                      title_split: str) -> List[str]: # 根据patterns中的匹配项递归拆分
    """按照patterns列表中的标题等级顺序 递归拆分文本"""
    paragraph = paragraph.strip()
    if not paragraph:
        return []
    if paragraph.find(prefix) == -1 and index > 0: # 必须从第一级标题开始加，否则会统一加上index=0的那部分文本
        title = potential_title(paragraph)
        if title not in titles_before:
            paragraph = titles_before + f"{prefix}"*max(0, index-1) + paragraph
        titles_before = titles_before + f"{prefix}"*max(0, index-1)+ title
    can_rec = True if index < len(patterns) - 1 else False
    sub_paragraph_list = []
    current_sub_paragraph = ""
    for sub_paragraph in re.split(patterns[index], paragraph):
        if can_rec:
            sub_paragraph_list.extend(get_sub_paragraph(prefix, titles_before, current_sub_paragraph, patterns, index+1, title_split))
        # else:
        #     sub_paragraph_list.append(current_sub_paragraph) # 用maxlength后需要把不能分割的加进去
        current_sub_paragraph = sub_paragraph
    if current_sub_paragraph:
        if can_rec:
            sub_paragraph_list.extend(get_sub_paragraph(prefix, titles_before, current_sub_paragraph, patterns, index+1, title_split))
        else:
            sub_paragraph_list.append(current_sub_paragraph)
    return sub_paragraph_list

def post_split_process(text: str, title_split: str) -> str:
    """
    把标题中的空格和换行去掉
    把文中多余的空格/换行替换成单一空格/换行    
    """
    text = text.replace('\n', title_split, 1)
    title_pos = text.find(title_split)
    if title_pos != -1:
        text = re.sub(r'\s+', '', text[:title_pos]) + text[title_pos:]
    
    text = re.sub(r' {2,}', ' ', text)
    text = re.sub(r' ?\n ?', '\n', text)
    text = re.sub(r'\n{2,}', '\n', text)
    return text

def clip_long_chapter(text:str, title_split :str, chunk_size: int = 1000, chunk_overlap:int = 50) -> List[str]:
    """把长的chapter切块"""
    if len(text) < chunk_size:
        return [text]
    title_pos = text.find(title_split)
    first_chunk = [text[:chunk_size]]
    if title_pos == -1:
        first_chunk.extend([text[i-chunk_overlap:i+chunk_size] for i in range(chunk_size, len(text), chunk_size)])
    first_chunk.extend([text[:title_pos+len(title_split)]+text[i-chunk_overlap:i+chunk_size] for i in range(chunk_size, len(text), chunk_size)])
    return first_chunk 


class ChineseChapterRecursiveSplitter(RecursiveCharacterTextSplitter):
    """
    按照标题等级大小递归切分文本，并把文本对应的所有等级的标题加载文本前
    paragraph -> [
        title_a1#title_a2** sub paragraph,
        title_b1** sub paragraph,
        title_b1#title_b2##title_b3** sub paragraph
    ]
    """
    def __init__(
                self,
                separators: Optional[List[str]] = None,
                keep_separator: bool = True,
                is_separator_regex: bool = True,
                **kwargs: Any,
        ) -> None:
            """Create a new TextSplitter."""
            # print("根据中文标题等级切分文本")
            super().__init__(keep_separator=keep_separator, **kwargs)
            self._separators = separators or Default_CATE_REPS
                                            #   r'\n{2,}']
            self._is_separator_regex = is_separator_regex
            self.title_prefix = "#" # 标记每一层title
            self.title_split = "**" # 分割titles和paragraph
    def get_seperators(self):
        return self._separators

    def split_documents(self, text: List[Document]) -> List[Document]:
        return text
    def pre_split_text(self, text: str, separators: List[str]=None) -> List[str]:
        chapters = [text]
        chapters = [sub_chapter for chapter in chapters for sub_chapter in get_sub_paragraph(prefix=self.title_prefix, 
                                                                                             titles_before='', 
                                                                                             paragraph=chapter.strip(), 
                                                                                             patterns=self._separators, 
                                                                                             index=0,
                                                                                             title_split=self.title_split)]

        chapters = [post_split_process(text=chapter, title_split=self.title_split) for chapter in chapters]
        chapter_min_len = 50
        chapters = [chapter for chapter in chapters if len(chapter) > chapter_min_len and chapter.find(self.title_split) != -1]
        chapters = [clipped_chapter for chapter in chapters for clipped_chapter in clip_long_chapter(text=chapter,
                                                                                                     title_split=self.title_split,
                                                                                                     chunk_size=self._chunk_size,
                                                                                                     chunk_overlap=self._chunk_overlap)]
        
        return chapters

if __name__ == "__main__":
    text_splitter = ChineseChapterRecursiveSplitter(
        keep_separator=True,
        is_separator_regex=True,
        chunk_size=200,
        chunk_overlap=10
    )
    ls = [
            "变速器#富勒RT11509C型变速箱的结构##“对齿”及对齿程序**为了解决双中间轴齿轮与主轴齿轮的正确啮合，必须“对齿”。\n所谓“对齿”，即组装变速器时，将两根中间轴传动齿轮上印有标记的轮齿\n分别插入输入轴(一轴)齿轮上印有标记的两组轮齿(每组包括相邻两个牙齿)的\n齿槽中，见图 22。\n1左中间轴传动齿轮 2右中间轴传动齿轮 3输入轴齿轮\n图 22 组装变速器总成对齿示意图\n副变速器“对齿”也按上述方法。\n通常是选用后面一对齿轮进行“对\n齿”。\n为了便于“对齿”，一般情况下，\n变速器的全部齿轮均为直齿，并且输\n入轴、主轴和输出轴上的齿轮均为偶\n数齿。\n“对齿”程序：\n1先在一轴齿轮的任意两个相\n邻齿上打记号，然后在与其相对称的\n另一侧两相邻齿上打上记号。两组记\n号间的齿数应相等。\n2在每只中间轴传动齿轮上与齿轮键槽正对的那个齿上打上记号，以便识\n别。\n3装配时使两只中间轴传动齿轮上有标记的齿分别啮入一轴齿轮左右两侧\n标有记号的两齿之中。"
        ]
    for inum, text in enumerate(ls):
        print(inum)
        chunks = text_splitter.split_text(text)
        for index, chunk in enumerate(chunks):
            print(index, chunk)
import docx
from typing import List
from langchain.document_loaders.unstructured import UnstructuredFileLoader
import os
import docx
from docx.document import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph
from docx.parts.image import ImagePart
from docx.image import Bmp,Png
from docx.oxml.shape import CT_Picture
from docx.image.image import Image


# 该行只能有一个图片
def is_image(graph:Paragraph,doc:Document):
    print("graph._element",graph._element)
    images = graph._element.xpath('.//pic:pic')  # 获取所有图片
    for image in images:
        for img_id in image.xpath('.//a:blip/@r:embed'):  # 获取图片id
            part = doc.part.related_parts[img_id]  # 根据图片id获取对应的图片
            if isinstance(part, ImagePart):
                return True
    return False
 
# 获取图片（该行只能有一个图片）
def get_ImagePart(graph:Paragraph,doc:Document):
    images = graph._element.xpath('.//pic:pic')  # 获取所有图片
    for image in images:
        for img_id in image.xpath('.//a:blip/@r:embed'):  # 获取图片id
            part = doc.part.related_parts[img_id]  # 根据图片id获取对应的图片
            if isinstance(part, ImagePart):
                return part 
    return None


def iter_block_items(parent):
    """
    Yield each paragraph and table child within *parent*, in document order.
    Each returned value is an instance of either Table or Paragraph. *parent*
    would most commonly be a reference to a main Document object, but
    also works for a _Cell object, which itself can contain paragraphs and tables.
    """
    if isinstance(parent, Document):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:
        raise ValueError("something's not right")

    for child in parent_elm.iterchildren():
        print(">>>>type",type(child),child)
        
        if isinstance(child, CT_P):
            paragraph=Paragraph(child, parent)
            if is_image(paragraph,parent):
                print('[Image] ')
                yield get_ImagePart(paragraph, parent)
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)
        elif isinstance(child,CT_Picture):
            yield Image(child,parent)
        else:
            print(">>>>type",type(child))
            pass

def read_table(table):
    return [[cell.text for cell in row.cells] for row in table.rows]


def read_word(word_path):
    doc = docx.Document(word_path)
    for block_index,block in enumerate(iter_block_items(doc)):
        if isinstance(block, Paragraph):
            print("text", [block.text],block)
        elif isinstance(block, Table):
            print("table", read_table(block),block.style)
        elif isinstance(block,Image):
            print("picture")
        # if block_index ==50:
        #     break



class CCDocxLoader(UnstructuredFileLoader):
    def _get_elements(self) -> List:
        read_word(self.file_path)
        return ""
            

if __name__ == "__main__":
    # loader = CCDocxLoader(file_path="/mnt/ddata/datasets/cc_data/ebook/核电/中广核/岭澳一期旋转滤网电机转速送主控显示改造详细设计-2019.06.17-仪控.docx")
    # eles = loader._get_elements()
    # for ele_index,els in enumerate(eles):
    #     print(ele_index,els,type(els))
    #     if ele_index >69:
    #         break
    import re
    doc = docx.Document("/mnt/ddata/datasets/cc_data/ebook/核电/中广核/岭澳一期旋转滤网电机转速送主控显示改造详细设计-2019.06.17-仪控.docx")
    pattern = re.compile('rId\d+')
        
    for block_index,block in enumerate(doc.paragraphs):
        print(block_index,block.text,type(block),block)
       
        for run_index, run in enumerate(block.runs):
            if run.text != '':
                print(run.text)
        else:
            # b.append(pattern.search(run.element.xml))
            print("run.element.xml",run.element.xml)
            groups = pattern.search(run.element.xml)
            if groups is None:
                continue
            contentID = groups.group(0)
            try:
                contentType = doc.part.related_parts[contentID].content_type
            except KeyError as e:
                print(e)
                continue
            if not contentType.startswith('image'):
                continue
            print("image")
        if block_index>100:
            break
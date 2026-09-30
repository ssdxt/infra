import logging
from openpyxl import load_workbook, Workbook
import openpyxl
import sys
from typing import Dict, List, Optional, Any
from io import BytesIO
import pandas as pd
import chardet
import json
import os
from schema import ChunkModel
from datetime import datetime, timedelta
from uuid import uuid4
import asyncio



all_codecs = [
    'utf-8', 'gb2312', 'gbk', 'utf_16', 'ascii', 'big5', 'big5hkscs',
    'cp037', 'cp273', 'cp424', 'cp437',
    'cp500', 'cp720', 'cp737', 'cp775', 'cp850', 'cp852', 'cp855', 'cp856', 'cp857',
    'cp858', 'cp860', 'cp861', 'cp862', 'cp863', 'cp864', 'cp865', 'cp866', 'cp869',
    'cp874', 'cp875', 'cp932', 'cp949', 'cp950', 'cp1006', 'cp1026', 'cp1125',
    'cp1140', 'cp1250', 'cp1251', 'cp1252', 'cp1253', 'cp1254', 'cp1255', 'cp1256',
    'cp1257', 'cp1258', 'euc_jp', 'euc_jis_2004', 'euc_jisx0213', 'euc_kr',
    'gb18030', 'hz', 'iso2022_jp', 'iso2022_jp_1', 'iso2022_jp_2',
    'iso2022_jp_2004', 'iso2022_jp_3', 'iso2022_jp_ext', 'iso2022_kr', 'latin_1',
    'iso8859_2', 'iso8859_3', 'iso8859_4', 'iso8859_5', 'iso8859_6', 'iso8859_7',
    'iso8859_8', 'iso8859_9', 'iso8859_10', 'iso8859_11', 'iso8859_13',
    'iso8859_14', 'iso8859_15', 'iso8859_16', 'johab', 'koi8_r', 'koi8_t', 'koi8_u',
    'kz1048', 'mac_cyrillic', 'mac_greek', 'mac_iceland', 'mac_latin2', 'mac_roman',
    'mac_turkish', 'ptcp154', 'shift_jis', 'shift_jis_2004', 'shift_jisx0213',
    'utf_32', 'utf_32_be', 'utf_32_le', 'utf_16_be', 'utf_16_le', 'utf_7', 'windows-1250', 'windows-1251',
    'windows-1252', 'windows-1253', 'windows-1254', 'windows-1255', 'windows-1256',
    'windows-1257', 'windows-1258', 'latin-2'
]


def find_codec(blob):
    detected = chardet.detect(blob[:1024])
    if detected['confidence'] > 0.5:
        return detected['encoding']

    for c in all_codecs:
        try:
            blob[:1024].decode(c)
            return c
        except Exception:
            pass
        try:
            blob.decode(c)
            return c
        except Exception:
            pass

    return "utf-8"


class ExcelLoader():
    def __init__(self, row_begin=1,row_end=99999,col_begin=1,col_end=99999,header_row: Optional[int] = None,**kwargs):
        self.row_begin = row_begin
        self.row_end = row_end
        self.col_begin = col_begin  
        self.col_end = col_end
        self.header_row = header_row  # 指定表头行号（相对于sheet，从1开始），None时自动寻找
    
    def find_header_row(self, rows):
        """
        寻找第一个有实际内容的行作为表头
        返回表头行的索引
        """
        for row_idx, row in enumerate(rows):
            # 检查这一行是否有非空内容
            has_content = False
            for col_idx, cell in enumerate(row):
                if col_idx >= self.col_begin-1 and col_idx < self.col_end:
                    if cell.value is not None and str(cell.value).strip():
                        has_content = True
                        break
            if has_content:
                return row_idx
        return 0  # 如果都没有内容，返回第一行
    
    # def load(self) -> List[Document]:
    async def parse(self,file_path, file_id,**kwargs):
        """
        加载excel文件并解析为Document对象列表，每一行生成一个chunk
        每行的page_content是JSON字符串格式的dict，表头为key
        每个chunk前面会加上"文件名__表单名"的前缀
        """
        chunks = []
        wb = ExcelLoader._load_excel_to_workbook(file_path)
        wb = self.unmerge_cell(wb)  # 将合并的单元格拆分
        
        # 提取文件名（不含路径和扩展名）
        if isinstance(file_path, str):
            file_name = os.path.splitext(os.path.basename(file_path))[0]
        else:
            file_name = "unknown"
        
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            update_time = datetime.utcnow() + timedelta(hours=8)
            
            # 获取所有行（根据row_begin和row_end范围）
            all_sheet_rows = list(ws.rows)
            rows = all_sheet_rows[self.row_begin-1:self.row_end]
            if not rows:
                continue
            
            # 确定表头行
            if self.header_row is not None:
                # 使用指定的表头行号（相对于sheet，从1开始）
                # 需要转换为相对于rows列表的索引
                header_row_absolute = self.header_row - 1  # 转换为0-based索引
                if header_row_absolute < self.row_begin - 1 or header_row_absolute >= self.row_end:
                    # 指定的表头行不在范围内，使用自动寻找
                    header_row_idx = self.find_header_row(rows)
                else:
                    # 计算在rows列表中的相对索引
                    header_row_idx = header_row_absolute - (self.row_begin - 1)
                    if header_row_idx < 0 or header_row_idx >= len(rows):
                        header_row_idx = self.find_header_row(rows)
            else:
                # 自动寻找有内容的表头行
                header_row_idx = self.find_header_row(rows)
            
            header_row = rows[header_row_idx]
            
            # 获取表头信息
            headers = []
            for idx, cell in enumerate(header_row):
                if idx >= self.col_begin-1 and idx < self.col_end:
                    # 只有当单元格有实际内容时才使用，否则使用默认列名
                    if cell.value is not None and str(cell.value).strip():
                        header_value = str(cell.value).strip()
                    else:
                        header_value = f"Column_{idx+1}"
                    headers.append(header_value)
                    
            # 处理数据行（跳过表头行），每一行生成一个Document
            for row_idx_in_rows, row in enumerate(rows):
                # 跳过表头行本身
                if row_idx_in_rows == header_row_idx:
                    continue
                
                # 计算实际行号（相对于sheet，从1开始）
                actual_row_number = self.row_begin + row_idx_in_rows
                
                # 构建行数据字典
                row_data = {}
                has_data = False
                
                for col_idx, cell in enumerate(row):
                    if col_idx >= self.col_begin-1 and col_idx < self.col_end:
                        value = str(cell.value) if cell.value is not None else ""
                        if value.strip():  # 检查是否有非空数据
                            has_data = True
                        
                        # 构建行数据字典，使用表头作为key
                        header_idx = col_idx - (self.col_begin-1)
                        if header_idx < len(headers):
                            row_data[headers[header_idx].replace("\n","")] = value
                
                # 跳过空行
                if not has_data:
                    continue
                
                # 将行数据转换为JSON字符串作为page_content
                row_data_json = json.dumps(row_data, ensure_ascii=False).replace("{","").replace("}","")
                # 在page_content前面加上"文件名__表单名"的前缀
                page_content = f"{file_name}_{sheet_name}\n{row_data_json}"
                
                chunk_id = f"{os.path.basename(file_path).split('.')[0][:10]}_{uuid4().hex}"
                
                chunks.append(
                    ChunkModel(
                        chunk_id=chunk_id,
                        chunk_index=actual_row_number,
                        content=page_content,
                        file_id=file_id,
                        file_path=file_path,
                        update_time=update_time.isoformat(),
                        bbox_type="text",
                        title=sheet_name,
                        media_path=""
                    )
                )

        return chunks, ""

    @staticmethod
    def _load_excel_to_workbook(file_like_object):
        try:
            
            if file_like_object.endswith("xlsx"):
                # 如果是xlsx文件
                file_like_object = BytesIO(file_like_object) if not isinstance(file_like_object, str) else file_like_object

            return load_workbook(file_like_object)
        except Exception as e:
            logging.info(f"****wxy: openpyxl load error: {e}, try pandas instead")
            try:
                # 读取xls文件，转换为xlsx
                if file_like_object.endswith("xls"):
                    from xls2xlsx import XLS2XLSX
                    # filename = "789.xls"
                    # outfile = "789.xlsx"
                    # Read xls file
                    x2x = XLS2XLSX(file_like_object)
                    # Write to xlsx file
                    x2x.to_xlsx(file_like_object[:-3]+"xlsx")
                    return load_workbook(file_like_object[:-3]+"xlsx")

                elif file_like_object.endswith("csv"):
                    # return load_workbook(file_like_object)
                    try:
                        df = pd.read_csv(file_like_object)
                    except:
                        df = pd.read_csv(file_like_object,encoding = 'gbk')
                    # df = pd.read_excel(file_like_object,encoding = 'gbk')
                    wb = Workbook()
                    ws = wb.active
                    ws.title = "Data"
                    for col_num, column_name in enumerate(df.columns, 1):
                        ws.cell(row=1, column=col_num, value=column_name)
                    for row_num, row in enumerate(df.values, 2):
                        for col_num, value in enumerate(row, 1):
                            ws.cell(row=row_num, column=col_num, value=value)
                    return wb
            
                raise Exception(f"目前只支持csv、xls、xlsx等格式")
            except Exception as e_pandas:
                raise Exception(f"你文件损坏了，换个试试")

    def unmerge_and_fill_cells(self,worksheet):
        all_merged_cell_ranges = list(
            worksheet.merged_cells.ranges
        )


        for merged_cell_range in all_merged_cell_ranges:
            merged_cell = merged_cell_range.start_cell
            worksheet.unmerge_cells(range_string=merged_cell_range.coord)
            for row_index, col_index in merged_cell_range.cells:

                cell = worksheet.cell(row=row_index, column=col_index)
                cell.value = merged_cell.value

    def unmerge_cell(self, wb):
        # wb = openpyxl.load_workbook(filename)
        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            self.unmerge_and_fill_cells(sheet)
            # print(sheet)
            # print(list(sheet.values))
        # filename = filename.replace(".xls", "_temp.xls")
        # wb.save(filename)
        # wb.close()

        return wb
    def __html(self, fnm, chunk_rows=256):
        # 不包括第 row_end 行
        # wb = RAGFlowExcelLoader._load_excel_to_workbook(file_like_object)
        wb = ExcelLoader._load_excel_to_workbook(fnm)
        wb = self.unmerge_cell(wb) # 将合并的单元格拆分
        tb_chunks = []
        sheets = []
        for sheetname in wb.sheetnames:
            sheets.append(sheetname)
            ws = wb[sheetname]
            rows = list(ws.rows)[self.row_begin-1:self.row_end]
            if not rows:
                continue

            header_values = [cell.value for cell in rows[0]]  # 获取第一行的值
            tb_rows_0 = "<tr>"
            first_value = rows[0][0].value
            for idx,t in enumerate(list(rows[0])):
                if idx!=0 and t.value == first_value:
                    break
                tb_rows_0 += f"<th>{t.value}</th>"
            tb_rows_0 += "</tr>"
            # print('0000000000000',(len(rows) - 1) // chunk_rows + 1)
            for chunk_i in range((len(rows) - 1) // chunk_rows + 1):
                tb = ""
                tb += f"<table><caption>{sheetname}</caption>"
                tb += tb_rows_0
                for r in list(
                  rows[1 + chunk_i * chunk_rows: 1 + (chunk_i + 1) * chunk_rows]
                ):                
                    row_values = [c.value for c in r][self.col_begin-1:self.col_end]
                    # **跳过所有值都等于第一行的行**
                    if row_values == header_values:
                        continue
                    tb += "<tr>"

                    for i, c in enumerate(row_values):
                    # for i, c in enumerate(r):

                        if c is None:
                            tb += "<td></td>"
                        else:
                            tb += f"<td>{c}</td>"
                    tb += "</tr>"
                tb += "</table>\n"
                tb_chunks.append(tb)

        return tb_chunks,sheets,

    def __call__(self, fnm):
        file_like_object = BytesIO(fnm) if not isinstance(fnm, str) else fnm
        wb = ExcelLoader._load_excel_to_workbook(file_like_object)

        res = []
        for sheetname in wb.sheetnames:
            ws = wb[sheetname]
            rows = list(ws.rows)
            if not rows:
                continue
            ti = list(rows[0])
            for r in list(rows[1:]):
                fields = []
                for i, c in enumerate(r):
                    # if not c.value:
                    #     continue
                    t = str(ti[i].value) if i < len(ti) else ""
                    t += ("：" if t else "") + str(c.value)
                    fields.append(t)
                line = "; ".join(fields)
                if sheetname.lower().find("sheet") < 0:
                    line += " ——" + sheetname
                res.append(line)
        return res

    @staticmethod
    def row_number(fnm, binary):
        if fnm.split(".")[-1].lower().find("xls") >= 0:
            wb = ExcelLoader._load_excel_to_workbook(BytesIO(binary))
            total = 0
            for sheetname in wb.sheetnames:
                ws = wb[sheetname]
                total += len(list(ws.rows))
            return total

        if fnm.split(".")[-1].lower() in ["csv", "txt"]:
            encoding = find_codec(binary)
            txt = binary.decode(encoding, errors="ignore")
            return len(txt.split("\n"))


async def main():
    
    file_path = "/mnt/ddata2/cc007/omniknow2/parser/rag/11111.csv"
    # file_path = "/mnt/ddata2/cc007/omniknow2/parser/rag/ttttttttttt.xls"
    # file_path = "/mnt/ddata2/cc007/omniknow2/parser/rag/melo.xlsx"
    parser = ExcelLoader()
    chunks = await parser.parse(
        file_path=file_path,
        file_id="15616156651",
        chunk_size=800,
        chunk_overlap=20,
        min_chunk_size=0,
        delimiters=["\n\n", "\n", "。", "；"]
    )
    print(chunks)


if __name__ == "__main__":
    asyncio.run(main())
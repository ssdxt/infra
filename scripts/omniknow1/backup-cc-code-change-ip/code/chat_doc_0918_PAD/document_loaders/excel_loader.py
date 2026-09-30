import logging
from openpyxl import load_workbook, Workbook
import openpyxl
import sys
from langchain.docstore.document import Document
from langchain.document_loaders.unstructured import UnstructuredFileLoader
from typing import Dict, List, Optional, Any
from io import BytesIO
import pandas as pd
import chardet



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

class ExcelLoader(UnstructuredFileLoader):
    def __init__(self, file_path: str or List[str], extract_image: bool = True, row_begin=1,row_end=99999,col_begin=1,col_end=99999,**kwargs):
        super().__init__(file_path, **kwargs)

        self.file_path = file_path
        self.row_begin = row_begin
        self.row_end = row_end
        self.col_begin = col_begin  
        self.col_end = col_end
    
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
    
    def load(self) -> List[Document]:
        """
        加载excel文件并解析为Document对象列表，根据第一列内容相同的行进行合并
        """
        docs = []
        wb = ExcelLoader._load_excel_to_workbook(self.file_path)
        wb = self.unmerge_cell(wb)  # 将合并的单元格拆分
        
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = list(ws.rows)[self.row_begin-1:self.row_end]
            if not rows:
                continue
                
            # 寻找有内容的表头行
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
            
            # 按第一列内容分组处理数据行
            grouped_rows = {}
            
            # 处理数据行（跳过表头行）
            for row_idx, row in enumerate(rows[header_row_idx+1:], start=header_row_idx+2):
                row_values = []
                row_data = {}
                
                # 提取指定列范围的数据
                has_data = False
                first_col_value = None
                
                for col_idx, cell in enumerate(row):
                    if col_idx >= self.col_begin-1 and col_idx < self.col_end:
                        value = str(cell.value) if cell.value is not None else ""
                        row_values.append(value)
                        if value.strip():  # 检查是否有非空数据
                            has_data = True
                        
                        # 获取第一列的值用于分组
                        if col_idx == self.col_begin-1:
                            first_col_value = value.strip()
                        
                        # 构建行数据字典
                        if col_idx - (self.col_begin-1) < len(headers):
                            row_data[headers[col_idx - (self.col_begin-1)]] = value
                
                # 跳过空行或第一列为空的行
                if not has_data or not first_col_value:
                    continue
                
                # 按第一列内容分组
                if first_col_value not in grouped_rows:
                    grouped_rows[first_col_value] = []
                
                grouped_rows[first_col_value].append({
                    'row_idx': row_idx,
                    'row_values': row_values,
                    'row_data': row_data
                })
            
            # 为每个分组生成Document
            for first_col_value, group_rows in grouped_rows.items():
                # 构建HTML表格内容
                header_html = "<tr>"
                for header in headers:
                    header_html += f"<th>{header}</th>"
                header_html += "</tr>"
                
                html_content = f"<table><caption>{sheet_name}</caption>"
                html_content += header_html
                
                # 添加该组的所有行
                merged_row_data = {}
                row_numbers = []
                
                for row_info in group_rows:
                    row_html = "<tr>"
                    for value in row_info['row_values']:
                        row_html += f"<td>{value}</td>"
                    row_html += "</tr>"
                    html_content += row_html
                    
                    # 收集所有行的数据到merged_row_data
                    for key, value in row_info['row_data'].items():
                        if key not in merged_row_data:
                            merged_row_data[key] = []
                        merged_row_data[key].append(value)
                    
                    row_numbers.append(row_info['row_idx'])
                
                html_content += "</table>"
                
                # 构建metadata，保持原有格式
                metadata = {
                    "content_pos": [{"page_no": 0, "left_top": 0, "right_bottom": {"x": 0, "y": 0}}],
                    "images": '',
                    "images_path": '',
                    "tables": [],
                    "titles": sheet_name,
                    "keyword": [],
                    "source": self.file_path,
                    "row_number": row_numbers,
                    "row_data": merged_row_data,
                    "headers": headers
                }
                
                docs.append(Document(page_content=html_content, metadata=metadata))
        
        return docs

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


if __name__ == "__main__":
    """
    目前支持csv、xlsx、xls等文件
        - csv只有一个sheet，不是只能处理一个表格，而是csv格式就是单表单格式
        - xlsx、xls可以有多个sheet，一张表单作为一个chunk
    处理逻辑：
        - 先补全单元格，将合并的单元格拆分
        - 再转成html格式
    """
    
    # path = "./test5.csv"
    # path = "./789.xls"
    path = "./333.xlsx"

    row_begin = 1
    row_end=5 # 包括第5行
    col_begin=1
    col_end=3 # 包括第3行
    
    # loader = ExcelLoader(path,row_begin=row_begin,row_end=row_end,col_begin=col_begin,col_end=col_end)
    loader = ExcelLoader(path)
    docs = loader.load()
    print(docs)
    
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Excel文件解析并上传到SQLite数据库

功能：
- 支持 .xlsx 和 .xls 格式
- 第一行作为列名
- 每个工作表创建一张表，表名使用工作表名
- 如果表已存在，先删除再创建（覆盖模式）
"""

import pandas as pd
import sqlite3
import os
import re
from pathlib import Path
from typing import Optional


class ExcelToSQLite:
    """Excel文件解析并导入SQLite数据库"""
    
    def __init__(self, excel_path: str, db_path: str):
        """
        初始化
        
        Args:
            excel_path: Excel文件路径
            db_path: SQLite数据库路径
        """
        self.excel_path = excel_path
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
    
    def _detect_file_format(self) -> str:
        """
        检测文件格式
        
        Returns:
            文件格式：'csv' 或 'excel'，不支持则抛出异常
        """
        file_ext = Path(self.excel_path).suffix.lower()
        if file_ext == '.csv':
            return 'csv'
        elif file_ext in ['.xlsx', '.xls']:
            return 'excel'
        else:
            raise ValueError(f"不支持的文件格式: {file_ext}。支持格式: .csv, .xlsx, .xls")
    
    
    def _read_csv_with_auto_encoding(self, file_path: str) -> pd.DataFrame:
        """
        自动检测编码读取CSV文件
        
        Args:
            file_path: CSV文件路径
            
        Returns:
            DataFrame对象
            
        Raises:
            ValueError: 如果所有编码都失败
        """
        # 常见编码列表，按优先级排序
        encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin1', 'cp1252', 'iso-8859-1']
        
        # 先尝试自动检测分隔符（使用utf-8）
        try:
            df = pd.read_csv(file_path, encoding='utf-8', sep=None, engine='python')
            return df
        except UnicodeDecodeError:
            # utf-8失败，尝试其他编码
            pass
        except Exception:
            # 其他错误（可能是分隔符问题），先尝试其他编码
            pass
        
        # 尝试其他编码
        last_error = None
        for encoding in encodings[1:]:  # 跳过已尝试的utf-8
            try:
                df = pd.read_csv(file_path, encoding=encoding, sep=None, engine='python')
                return df
            except UnicodeDecodeError:
                last_error = f"编码 {encoding} 解码失败"
                continue
            except Exception as e:
                # 如果是其他错误（如分隔符问题），使用当前编码再试一次，使用默认分隔符
                try:
                    df = pd.read_csv(file_path, encoding=encoding, sep=',', engine='python')
                    return df
                except Exception:
                    last_error = str(e)
                    continue
        
        # 所有编码都失败
        raise ValueError(f"无法读取CSV文件，尝试的编码都失败。最后错误: {last_error}")
    
    def _sanitize_table_name(self, name: str) -> str:
        """
        清理表名，使其符合SQLite命名规范
        
        Args:
            name: 原始表名
            
        Returns:
            清理后的表名
        """
        # 移除或替换非法字符
        # SQLite允许的字符：字母、数字、下划线，不能以数字开头
        # 将非法字符替换为下划线
        sanitized = re.sub(r'[^\w]', '_', name)
        # 如果以数字开头，添加前缀
        if sanitized and sanitized[0].isdigit():
            sanitized = 'table_' + sanitized
        # 如果为空，使用默认名称
        if not sanitized:
            sanitized = 'sheet'
        return sanitized
    
    def _sanitize_column_name(self, name: str) -> str:
        """
        清理列名，使其符合SQLite命名规范
        
        Args:
            name: 原始列名
            
        Returns:
            清理后的列名
        """
        # 处理空值
        if pd.isna(name) or name == '':
            return 'unnamed_column'
        
        # 转换为字符串
        name = str(name).strip()
        
        # 移除或替换非法字符
        sanitized = re.sub(r'[^\w]', '_', name)
        
        # 如果以数字开头，添加前缀
        if sanitized and sanitized[0].isdigit():
            sanitized = 'col_' + sanitized
        
        # 如果为空，使用默认名称
        if not sanitized:
            sanitized = 'unnamed_column'
        
        return sanitized
    
    def _get_sqlite_type(self, dtype) -> str:
        """
        根据pandas数据类型推断SQLite类型
        
        Args:
            dtype: pandas数据类型
            
        Returns:
            SQLite类型字符串
        """
        if pd.api.types.is_integer_dtype(dtype):
            return 'INTEGER'
        elif pd.api.types.is_float_dtype(dtype):
            return 'REAL'
        elif pd.api.types.is_datetime64_any_dtype(dtype):
            return 'TEXT'  # SQLite没有专门的日期类型，使用TEXT存储ISO格式
        elif pd.api.types.is_bool_dtype(dtype):
            return 'INTEGER'  # SQLite用0/1表示布尔值
        else:
            return 'TEXT'
    
    def _create_table(self, cursor: sqlite3.Cursor, table_name: str, df: pd.DataFrame):
        """
        创建表（如果存在则先删除）
        
        Args:
            cursor: 数据库游标
            table_name: 表名
            df: DataFrame数据
        """
        # 删除已存在的表
        cursor.execute(f'DROP TABLE IF EXISTS "{table_name}"')
        
        # 构建CREATE TABLE语句
        columns = []
        for col in df.columns:
            col_name = self._sanitize_column_name(col)
            col_type = self._get_sqlite_type(df[col].dtype)
            columns.append(f'"{col_name}" {col_type}')
        
        create_sql = f'CREATE TABLE "{table_name}" ({", ".join(columns)})'
        cursor.execute(create_sql)
    
    def _insert_data(self, cursor: sqlite3.Cursor, table_name: str, df: pd.DataFrame):
        """
        插入数据到表
        
        Args:
            cursor: 数据库游标
            table_name: 表名
            df: DataFrame数据
        """
        # 清理列名
        df_clean = df.copy()
        df_clean.columns = [self._sanitize_column_name(col) for col in df.columns]
        
        # 处理日期时间类型，转换为字符串（ISO格式）
        for col in df_clean.columns:
            if pd.api.types.is_datetime64_any_dtype(df_clean[col]):
                df_clean[col] = df_clean[col].dt.strftime('%Y-%m-%d %H:%M:%S')
        
        # 处理NaN值，替换为None（SQLite的NULL）
        df_clean = df_clean.where(pd.notnull(df_clean), None)
        
        # 构建INSERT语句
        placeholders = ', '.join(['?' for _ in df_clean.columns])
        columns_str = ', '.join([f'"{col}"' for col in df_clean.columns])
        insert_sql = f'INSERT INTO "{table_name}" ({columns_str}) VALUES ({placeholders})'
        
        # 批量插入数据，将Timestamp等类型转换为Python原生类型
        data_tuples = []
        for row in df_clean.values:
            # 转换每一行的数据，将pandas特殊类型转换为Python原生类型
            converted_row = []
            for val in row:
                if pd.isna(val):
                    converted_row.append(None)
                elif isinstance(val, pd.Timestamp):
                    converted_row.append(val.strftime('%Y-%m-%d %H:%M:%S'))
                elif isinstance(val, (pd.Int64Dtype, pd.Float64Dtype)):
                    converted_row.append(val.item() if hasattr(val, 'item') else val)
                else:
                    converted_row.append(val)
            data_tuples.append(tuple(converted_row))
        
        cursor.executemany(insert_sql, data_tuples)
    
    def process(self):
        """
        处理Excel文件并导入SQLite数据库
        
        Returns:
            dict: 处理结果统计信息
        """
        # 检查Excel文件是否存在
        if not os.path.exists(self.excel_path):
            raise FileNotFoundError(f"Excel文件不存在: {self.excel_path}")
        
        file_format = self._detect_file_format()
        file_name = Path(self.excel_path).stem
        
        # 连接数据库
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()
        
        results = {
            'total_sheets': 0,
            # 'total_sheets': len(excel_file.sheet_names),
            'processed_sheets': [],
            'errors': []
        }
        
 
        try:
            if file_format == 'csv':
                # 处理CSV文件
                try:
                    # 自动检测编码和分隔符
                    df = self._read_csv_with_auto_encoding(self.excel_path)
                    
                    # 跳过空表
                    if df.empty:
                        results['processed_sheets'].append({
                            'sheet_name': file_name,
                            'table_name': None,
                            'rows': 0,
                            'status': 'skipped (empty)'
                        })
                    else:
                        # 清理表名（仅使用文件名，不含扩展名）
                        table_name = self._sanitize_table_name(file_name)
                        
                        # 创建表
                        self._create_table(cursor, table_name, df)
                        
                        # 插入数据
                        self._insert_data(cursor, table_name, df)
                        
                        # 提交事务
                        self.conn.commit()
                        
                        results['total_sheets'] = 1
                        results['processed_sheets'].append({
                            'sheet_name': file_name,
                            'table_name': table_name,
                            'rows': len(df),
                            'columns': len(df.columns),
                            'status': 'success'
                        })
                        
                        print(f"✓ CSV文件 '{file_name}' -> 表 '{table_name}' ({len(df)} 行, {len(df.columns)} 列)")
                
                except Exception as e:
                    error_msg = f"处理CSV文件时出错: {str(e)}"
                    results['errors'].append(error_msg)
                    print(f"✗ {error_msg}")
                    self.conn.rollback()
            else:
                # 读取Excel文件
                try:
                    excel_file = pd.ExcelFile(self.excel_path, engine=None)
                except Exception as e:
                    raise ValueError(f"无法读取Excel文件: {e}")
                
                results['total_sheets'] = len(excel_file.sheet_names)
                
                # 处理每个工作表
                for sheet_name in excel_file.sheet_names:
                    try:
                        # 读取工作表数据
                        df = pd.read_excel(excel_file, sheet_name=sheet_name)
                        
                        # 跳过空表
                        if df.empty:
                            results['processed_sheets'].append({
                                'sheet_name': sheet_name,
                                'table_name': None,
                                'rows': 0,
                                'status': 'skipped (empty)'
                            })
                            continue
                        
                        # 清理表名
                        table_name = self._sanitize_table_name(file_name + '-' + sheet_name)
                        
                        # 创建表
                        self._create_table(cursor, table_name, df)
                        
                        # 插入数据
                        self._insert_data(cursor, table_name, df)
                        
                        # 提交事务
                        self.conn.commit()
                        
                        results['processed_sheets'].append({
                            'sheet_name': sheet_name,
                            'table_name': table_name,
                            'rows': len(df),
                            'columns': len(df.columns),
                            'status': 'success'
                        })
                        
                        print(f"✓ 工作表 '{sheet_name}' -> 表 '{table_name}' ({len(df)} 行, {len(df.columns)} 列)")
                        
                    except Exception as e:
                        error_msg = f"处理工作表 '{sheet_name}' 时出错: {str(e)}"
                        results['errors'].append(error_msg)
                        print(f"✗ {error_msg}")
                        # 回滚当前工作表的操作
                        self.conn.rollback()
            
        finally:
            # 关闭数据库连接
            if self.conn:
                self.conn.close()
        
        return results
    
    def print_summary(self, results: dict):
        """
        打印处理结果摘要
        
        Args:
            results: 处理结果统计信息
        """
        print("\n" + "="*60)
        print("处理完成！")
        print("="*60)
        if results['total_sheets'] > 0:
            print(f"总工作表/文件数: {results['total_sheets']}")
        
        print(f"成功处理: {len([s for s in results['processed_sheets'] if s['status'] == 'success'])}")
        print(f"错误数: {len(results['errors'])}")
        print("\n详细结果:")
        for sheet in results['processed_sheets']:
            if sheet['status'] == 'success':
                print(f"  - {sheet['sheet_name']} -> {sheet['table_name']} "
                      f"({sheet['rows']} 行, {sheet['columns']} 列)")
            else:
                print(f"  - {sheet['sheet_name']}: {sheet['status']}")
        
        if results['errors']:
            print("\n错误信息:")
            for error in results['errors']:
                print(f"  - {error}")
        print("="*60)


def main():
    """主函数"""
    # 配置路径
    EXCEL_PATH = './发动机.xlsx'
    # EXCEL_PATH = './ttttt.xls'
    # EXCEL_PATH = './adasd.csv'
    DB_PATH = './data.db'
    
    # 创建处理器并执行
    processor = ExcelToSQLite(EXCEL_PATH, DB_PATH)
    
    try:
        results = processor.process()
        processor.print_summary(results)
    except Exception as e:
        print(f"错误: {e}")
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
    # from pathlib import Path

    # path = Path("/home/user/data/example.txt")
    # stem = path.stem
    # print(stem)  # example


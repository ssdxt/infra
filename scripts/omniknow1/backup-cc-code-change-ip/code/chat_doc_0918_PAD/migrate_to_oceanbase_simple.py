import sqlite3
import pymysql
import sys
from datetime import datetime

# 数据库配置
SQLITE_DB_PATH = './knowledge_base/info.db'#替换为实际路径
OCEANBASE_CONFIG = {
    'host': '192.168.21.111',
    'port': 2881,
    'user': 'root@test',
    'password': '12345',
    'database': 'chat_doc',
    'charset': 'utf8mb4'
}

# SQLite到MySQL的数据类型映射
TYPE_MAPPING = {
    'INTEGER': 'INT',
    'TEXT': 'LONGTEXT',
    'REAL': 'DOUBLE',
    'BLOB': 'LONGBLOB',
    'NUMERIC': 'DECIMAL',
    'VARCHAR(2048)': 'LONGTEXT',
    'VARCH(256)': 'VARCHAR(256)',
    'VARCH(1024)': 'VARCHAR(1024)',
    'VARCH(2048)': 'VARCHAR(2048)',
    'varchar(256)': 'VARCHAR(256)',
    'DATETIME': 'DATETIME',
    'TIMESTAMP': 'TIMESTAMP',
    'BOOLEAN': 'TINYINT(1)',
    'JSON': 'JSON'
}

def get_sqlite_table_schema(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    
    schema_parts = []
    for col in columns:
        col_name = col[1]
        col_type = col[2]
        not_null = col[3]
        default_value = col[4]
        is_pk = col[5]
        
        # 映射数据类型
        mysql_type = TYPE_MAPPING.get(col_type.upper(), col_type)
        
        # 特殊处理：更精确地识别JSON字段
        # 只有字段名明确包含json或者原始类型就是JSON时才转换
        if ('json' in col_name.lower() and 'type' in col_name.lower()) or col_type.upper() == 'JSON':
            mysql_type = 'JSON'
        
        # 构建列定义
        col_def = f"`{col_name}` {mysql_type}"
        
        # 处理主键 - 根据字段类型和名称智能判断是否需要AUTO_INCREMENT
        if is_pk:
            # 只有数字类型的id字段才使用AUTO_INCREMENT
            if (mysql_type.upper() in ['INT', 'BIGINT', 'SMALLINT', 'TINYINT'] and 
                col_name.lower() == 'id'):
                col_def += " AUTO_INCREMENT PRIMARY KEY"
            else:
                # 字符串类型的主键或非id字段的主键不使用AUTO_INCREMENT
                col_def += " PRIMARY KEY"
        
        # 处理默认值 - JSON、LONGTEXT、TEXT、BLOB等类型不能有默认值
        if (default_value is not None and 
            mysql_type.upper() not in ['JSON', 'LONGTEXT', 'TEXT', 'MEDIUMTEXT', 'LONGBLOB', 'MEDIUMBLOB', 'BLOB']):
            # 特殊处理 CURRENT_TIMESTAMP 等函数
            if default_value.upper() in ['CURRENT_TIMESTAMP', 'NOW()', 'CURRENT_DATE', 'CURRENT_TIME']:
                col_def += f" DEFAULT {default_value.upper()}"
            else:
                # 移除已有的引号并重新添加
                clean_default = str(default_value).strip("'\"")
                col_def += f" DEFAULT '{clean_default}'"
        
        if not_null and not is_pk:
            col_def += " NOT NULL"
            
        schema_parts.append(col_def)
    
    return schema_parts

def create_table_in_oceanbase(oceanbase_cursor, table_name, schema):
    """在OceanBase中创建表"""
    # 删除已存在的表
    drop_sql = f"DROP TABLE IF EXISTS `{table_name}`"
    oceanbase_cursor.execute(drop_sql)
    
    # 创建新表
    schema_str = ',\n  '.join(schema)
    create_sql = f"CREATE TABLE `{table_name}` (\n  {schema_str}\n) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci"
    
    print(f"创建表 {table_name}:")
    print(create_sql)
    print()
    
    oceanbase_cursor.execute(create_sql)

def migrate_table_data(sqlite_cursor, oceanbase_cursor, table_name):
    """迁移表数据"""
    # 获取SQLite表的所有数据
    sqlite_cursor.execute(f"SELECT * FROM {table_name}")
    rows = sqlite_cursor.fetchall()
    
    if not rows:
        print(f"表 {table_name} 没有数据")
        return 0
    
    # 获取列名
    sqlite_cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [col[1] for col in sqlite_cursor.fetchall()]
    
    # 构建插入SQL
    placeholders = ', '.join(['%s'] * len(columns))
    column_names = ', '.join([f"`{col}`" for col in columns])
    insert_sql = f"INSERT INTO `{table_name}` ({column_names}) VALUES ({placeholders})"
    
    # 批量插入数据
    migrated_count = 0
    for row in rows:
        try:
            # 处理时间字段和长文本字段
            processed_row = []
            for value in row:
                if isinstance(value, str):
                    if len(value) == 19 and value.count('-') == 2 and value.count(':') == 2:
                        try:
                            datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
                            processed_row.append(value)
                        except ValueError:
                            processed_row.append(value)
                    else:
                        processed_row.append(value)
                else:
                    processed_row.append(value)
            
            oceanbase_cursor.execute(insert_sql, processed_row)
            migrated_count += 1
        except Exception as e:
            print(f"插入数据时出错 (表: {table_name}): {e}")
            print(f"问题数据长度: {len(str(row))} 字符")
            continue
    
    return migrated_count

def main():
    try:
        # 连接SQLite数据库
        sqlite_conn = sqlite3.connect(SQLITE_DB_PATH)
        sqlite_cursor = sqlite_conn.cursor()
        
        # 连接OceanBase数据库
        oceanbase_conn = pymysql.connect(**OCEANBASE_CONFIG)
        oceanbase_cursor = oceanbase_conn.cursor()
        
        # 获取SQLite中的所有表
        sqlite_cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        all_tables = [table[0] for table in sqlite_cursor.fetchall()]
        
        # 过滤掉系统表
        system_tables = ['sqlite_sequence', 'sqlite_master', 'sqlite_temp_master']
        tables = [table for table in all_tables if table not in system_tables]
        
        print(f"发现 {len(all_tables)} 个表，跳过 {len(all_tables) - len(tables)} 个系统表")
        print(f"需要迁移的表: {tables}")
        print("="*50)
        
        total_migrated = 0
        
        for table_name in tables:
            print(f"\n处理表: {table_name}")
            
            # 获取表结构
            schema = get_sqlite_table_schema(sqlite_cursor, table_name)
            
            # 在OceanBase中创建表
            create_table_in_oceanbase(oceanbase_cursor, table_name, schema)
            
            # 迁移数据
            migrated_count = migrate_table_data(sqlite_cursor, oceanbase_cursor, table_name)
            total_migrated += migrated_count
            
            print(f"表 {table_name} 迁移完成，共 {migrated_count} 条记录")
            
            oceanbase_conn.commit()
        
        print("\n" + "="*50)
        print(f"迁移完成！总共迁移了 {total_migrated} 条记录")
        
        print("\n验证迁移结果:")
        for table_name in tables:
            oceanbase_cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`")
            count = oceanbase_cursor.fetchone()[0]
            print(f"表 {table_name}: {count} 条记录")
        
    except Exception as e:
        print(f"迁移过程中出现错误: {e}")
        sys.exit(1)
    
    finally:
        if 'sqlite_conn' in locals():
            sqlite_conn.close()
        if 'oceanbase_conn' in locals():
            oceanbase_conn.close()

if __name__ == "__main__":
    main()

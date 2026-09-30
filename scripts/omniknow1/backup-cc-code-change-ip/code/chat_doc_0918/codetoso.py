from distutils.core import setup
from Cython.Build import cythonize
import os
import glob
import sys

def get_all_python_files(folder_path):
    """
    递归获取文件夹中的所有Python文件
    """
    python_files = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.py') and file != 'setup.py' and file != 'codetoso.py':
                file_path = os.path.join(root, file)
                python_files.append(file_path)
    return python_files

os.makedirs("build", exist_ok=True)

if len(sys.argv) > 1 and sys.argv[1] == 'batch':
    # 批量加密模式
    if len(sys.argv) < 3:
        print("使用方法: python codetoso.py batch <文件夹路径>")
        print("示例: python codetoso.py batch ./document_loaders")
        sys.exit(1)
    
    folder_path = sys.argv[2]
    if not os.path.exists(folder_path):
        print(f"错误：文件夹 {folder_path} 不存在")
        sys.exit(1)
    
    python_files = get_all_python_files(folder_path)
    
    if not python_files:
        print(f"在文件夹 {folder_path} 中没有找到Python文件")
        sys.exit(1)
    
    print(f"找到 {len(python_files)} 个Python文件：")
    for file in python_files:
        print(f"  - {file}")
    
    setup(
        ext_modules=cythonize(
            python_files,
            compiler_directives={
                'language_level': 3,
                'binding': True,  # 启用绑定模式
                'embedsignature': True,  # 嵌入签名信息
                'always_allow_keywords': True,  # 允许关键字参数
                'annotation_typing': False,  # 禁用类型注解检查
            }
        ),
        script_args=['build_ext', '--inplace']
    )
    print(f"批量加密完成！")
else:
    source_files = [
    "./server/api.py",
    "./server/chat/time_validator.py",
    "./server/chat/knowledge_base_chat.py",
    "./server/knowledge_base/kb_doc_api.py",
    "./server/knowledge_base/kb_api.py",
    "./version_update.py"
]
    setup(
        ext_modules = cythonize(
            source_files,
            # ["/deploy/code/chat_doc_0520/server/knowledge_base/kb_doc_api.py"],
            compiler_directives={
                'language_level': 3,
                'binding': True,  # 启用绑定模式
                'embedsignature': True,  # 嵌入签名信息
                'always_allow_keywords': True,  # 允许关键字参数
                'annotation_typing': False,  # 禁用类型注解检查
            }),
        script_args=['build_ext', '--inplace'])

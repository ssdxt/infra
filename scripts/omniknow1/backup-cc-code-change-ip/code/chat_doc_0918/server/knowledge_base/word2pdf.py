import subprocess
import os
# os.environ["TOKENIZERS_PARALLELISM"] = "false"
# from configs import logger


def doc2pdf_linux(doc):
    """
    convert a doc/docx document to pdf format (linux only, requires libreoffice)
    :param doc: path to document
    """
    pdf_dir = doc[:str(doc).rfind("/")]
    pdf_dir = pdf_dir[:str(pdf_dir).rfind("/")]+"/"+"content"
    print("pdf_dir:",pdf_dir)
    cmd = 'libreoffice --convert-to pdf'.split() + [doc] +["--outdir",pdf_dir]
    print(type(cmd),cmd)
    p = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    p.wait(timeout=200)
    stdout, stderr = p.communicate()
    
    # 检查是否有错误输出
    if stderr:
        # 将字节转换为字符串
        stderr_str = stderr.decode('utf-8', errors='replace')
        
        # 如果错误只包含无效转义序列警告，则忽略它
        if "SyntaxWarning: invalid escape sequence" in stderr_str and "javasettings.py" in stderr_str:
            # 这只是一个警告，不是真正的错误，可以忽略
            print("忽略 LibreOffice 的语法警告:", stderr_str)
        else:
            # 其他错误则正常抛出
            raise subprocess.SubprocessError(stderr)

def doc2pdf(doc):
    """
    convert a doc/docx document to pdf format
    :param doc: path to document
    """
    doc = os.path.abspath(doc) # bugfix - searching files in windows/system32
    
    try:
        from comtypes import client
    except ImportError as e:
        client = None
        # logger.exception(e)
    
    if client is None:
        return doc2pdf_linux(doc)
    name, ext = os.path.splitext(doc)
    try:
        word = client.CreateObject('Word.Application')
        worddoc = word.Documents.Open(doc)
        worddoc.SaveAs(name + '.pdf', FileFormat=17)
    except Exception:
        raise
    finally:
        worddoc.Close()
        word.Quit()



if __name__ == "__main__":
    doc2pdf("knowledge_base/lb_test/content/陕汽L3000系列载货车维修手册（第一部分）.docx")
import subprocess
import os
from pathlib import Path

def pptx2pdf(input_pptx):
    """
    使用 LibreOffice 将 PPTX 转换为 PDF。
    
    Args:
        input_pptx (str): 输入的 PPTX 文件路径。
    """
    import os
    from pathlib import Path
    import subprocess

    # 确保输入文件存在
    if not os.path.exists(input_pptx):
        raise FileNotFoundError(f"Input file {input_pptx} does not exist.")

    # 获取输出 PDF 文件路径
    output_dir = Path(input_pptx).parent
    output_pdf = output_dir / (Path(input_pptx).stem + ".pdf")

    # 使用 LibreOffice 转换
    try:
        print(f"Converting {input_pptx} to {output_pdf} using LibreOffice...")
        subprocess.run(
            [
                "libreoffice",
                "--headless",  # 无需 GUI
                "--convert-to", "pdf",  # 转换格式为 PDF
                input_pptx,
                "--outdir", str(output_dir)
            ],
            check=True
        )
        print(f"PDF successfully created at {output_pdf}")
    except subprocess.CalledProcessError as e:
        print(f"Error during conversion: {e}")
        raise RuntimeError("LibreOffice conversion failed.") from e


def ppt_to_pptx(input_file):
    """
    使用 LibreOffice 将 .ppt 文件转换为 .pptx 文件。

    :param input_file: 输入的 .ppt 文件路径
    :param output_dir: 输出文件的存放目录
    """

    # 获取输出 pptx 文件路径
    output_dir = Path(input_file).parent
    output_pptx = output_dir / (Path(input_file).stem + ".pptx")

    # 确保输出目录存在
    output_dir.mkdir(parents=True, exist_ok=True)

    # 构造命令行参数
    cmd = [
        "soffice",
        "--headless",
        "--convert-to", "pptx:Impress MS PowerPoint 2007 XML",
        input_file,
        "--outdir", str(output_dir)
    ]
    # 执行命令
    subprocess.run(cmd, check=True)
    # 验证文件是否生成
    if not output_pptx.exists():
        raise FileNotFoundError(f"转换失败，未生成文件: {output_pptx}")
    return output_pptx


# 示例用法
if __name__ == "__main__":
    input_pptx = "2.pptx"  # 输入文件
    output_pdf = "output/2.pdf"  # 输出文件
    print(pptx2pdf(input_pptx))


from markdownify import markdownify as md
import argparse
import sys
import re
from pathlib import Path

START_PATTERNS = [
    r"\*\*注意：\*\*",
    r"注意：",
    r"^\s*注\s*$",
    r"^\s*警告\s*$",
    r"Warning Icon",
]

start_re = re.compile("|".join(START_PATTERNS))

def remove_notice_warning(md_text: str) -> str:
    lines = md_text.splitlines()
    result = []
    skip = False

    for line in lines:
        # 进入注意 / 警告块
        if start_re.search(line):
            skip = True
            continue

        # 退出条件：空行 + 非缩进正文 / 新步骤 / 新标题
        if skip:
            if (
                line.strip() == "" or
                re.match(r"^\s*\d+\.\s+", line) or  # 步骤 1. 2.
                re.match(r"^#+\s+", line) or        # Markdown 标题
                re.match(r"^[^\s]", line)           # 顶格内容
            ):
                skip = False
                result.append(line)
            continue

        result.append(line)

    return "\n".join(result)




def convert_html_to_md(html_content):
    """将HTML内容转换为Markdown格式"""
    try:
        return md(html_content)
    except Exception as e:
        print(f"转换过程中发生错误: {str(e)}")
        return None

def html_file_to_md(input_file, output_file):
    """将HTML文件转换为Markdown文件"""
    try:
        # with open(input_file, 'r', encoding='utf-8') as f:
        #     html_content = f.read()
        html_content="""<table><tr><td rowspan=1 colspan=1>部件名称</td><td rowspan=1 colspan=1>左前车门饰板 (右侧同)</td></tr><tr><td rowspan=1 colspan=1>位置</td><td rowspan=1 colspan=1>见图示</td></tr><tr><td rowspan=1 colspan=1>材料</td><td rowspan=1 colspan=1>PP,TPO,PC+ABS,PP/PE，麻纤维，PET，钢，胶水等</td></tr><tr><td rowspan=1 colspan=1>数量</td><td rowspan=1 colspan=1>1</td></tr><tr><td rowspan=1 colspan=1>重量 (KG)</td><td rowspan=1 colspan=1>3.6</td></tr><tr><td rowspan=1 colspan=1>紧固件</td><td rowspan=1 colspan=1>夹子，螺钉</td></tr><tr><td rowspan=1 colspan=1>紧固件数</td><td rowspan=1 colspan=1>螺钉*3</td></tr><tr><td rowspan=1 colspan=1>拆解工具</td><td rowspan=1 colspan=1>无绳棘轮/冲击钻，梅花 T30 套筒6 英寸加长件，棘轮/扭矩扳手</td></tr><tr><td rowspan=1 colspan=1>拆解方法</td><td rowspan=1 colspan=1>打开左前车门，完全降下车窗。将反光灯从左前车门饰板后边缘拆下。拆卸将饰板固定到车门的螺钉 (3 个)。拆卸左前车门扬声器。拆卸左前车门地面照明灯。从地面照明灯开口处拉出饰板，以便松开将饰板固定到车门的卡子。继续拉动，并从下至上松开饰板边缘的所有卡子。从缆索支架上松开手动释放缆索，将缆索卡环从饰板上拆下，然后向下转动卡环至垂直方向。将缆索接线管末端滑出释放杆，然后将缆索从饰板上拆下。将电气线束从车门连接器上断开。抬起饰板，使其与车门脱钩，然后将饰板从车门上拆下。</td></tr><tr><td rowspan=1 colspan=1>回收利用途径</td><td rowspan=1 colspan=1>废塑料改性后再利用</td></tr></table>"""
        markdown_content = convert_html_to_md(html_content)
        if markdown_content is None:
            return False
        
        print(markdown_content)
        print(type(markdown_content))
        # with open(output_file, 'w', encoding='utf-8') as f:
        #     f.write(markdown_content)
        return True
        
    except FileNotFoundError:
        print(f"错误: 输入文件 {input_file} 不存在")
    except Exception as e:
        print(f"处理文件时发生错误: {str(e)}")
    return False

def main():
    parser = argparse.ArgumentParser(description='HTML转Markdown工具')
    parser.add_argument('--input', default="/mnt/ddata2/cc007/omniknow2/parser/rag/123.html",help='输入的HTML文件路径')
    parser.add_argument('--output', default="/mnt/ddata2/cc007/omniknow2/parser/rag/123.md",help='输出的Markdown文件路径')
    args = parser.parse_args()
    
    if html_file_to_md(args.input, args.output):
        print(f"转换成功! 结果已保存到 {args.output}")



def pose_process(text:str):
    mark = "© Tesla\n2025\nC"

    idx = s.find(mark)
    if idx != -1:
        s = s[:idx]
    
    return s.replace("请参阅\n", "请参阅").replace("\n。", "。").replace("Torque Calculator\n", "")


if __name__ == '__main__':
    main()
    # md_path = Path("123.md")
    # text = md_path.read_text(encoding="utf-8")

    # clean_text = remove_notice_warning(text)

    # Path("output.md").write_text(clean_text, encoding="utf-8")

    # s = "Torque Calculator\n2023-10-20\n驾驶位气囊线束总成 ((拆卸和更换))\n校正代码\n2001010062\nFRT\n0.12\n注意：\n请参阅\n人体工程学注意事项\n查看安全健康的作业规程。\n父主题：\n2001 - 气囊\n拆卸\n拆卸前备箱后部挡板。请参阅\n后裙板总成 ((拆卸和更换))\n。\n断开低压电源。请参阅\n低压电池 - 锂离子（断开和连接）\n。\n拆卸驾驶位气囊。请参阅\n驾驶位气囊总成 ((拆卸和更换))\n。\n使用保护胶带完全遮盖气囊朝向驾驶位的一侧。\n将驾驶位气囊放置在干净的作业表面上。\n松开将驾驶位气囊线束固定到气囊的锁片和定位卡子（2 个）。\n将电气线束连接器从驾驶位气囊上断开 。\n安装\n将驾驶位气囊线束连接器与驾驶位气囊相连，然后安装锁片和定位卡子（2 个）。\n揭下气囊上的保护胶带。\n安装驾驶位气囊。请参阅\n驾驶位气囊总成 ((拆卸和更换))\n。\n连接低压电源。请参阅\n低压电池 - 锂离子（断开和连接）\n。\n安装前备箱后部挡板。请参阅\n后裙板总成 ((拆卸和更换))\n。\n© Tesla\n2025\nCrowsfoot or Offset Wrench Extension Calculator\nChange to Metric\nTorque Calculator Values\nT1 (Original torque spec)\nL (Distance from center of wrench grip to center of square drive tang)\nE (Horizontal distance from center of square drive tang to center of fastener)\nT2 (Final torque setting)>\nFigure 1\nFigure 2\nFigure 3"
    
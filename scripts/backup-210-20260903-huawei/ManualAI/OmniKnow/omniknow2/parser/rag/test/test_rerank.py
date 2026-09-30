import asyncio
from typing import Union, List
from openai import AsyncOpenAI
from dotenv import load_dotenv
import numpy as np
import httpx
import os
load_dotenv()

embedding_dimensions = int(os.getenv("EMBEDDING_DIMENSIONS"))
embedding_max_len = int(os.getenv("EMBEDDING_MAX_LEN"))
embedding_batch_size = int(os.getenv("EMBEDDING_BATCH_SIZE"))
embedding_model = os.getenv("EMBEDDING_MODEL")
embedding_client = AsyncOpenAI(
                        base_url=os.getenv("EMBEDDING_BASE_URL"),
                        api_key=os.getenv("EMBEDDING_KEY")
                    )

rerank_max_len = int(os.getenv("RERANK_MAX_LEN"))
rerank_key = os.getenv("RERANK_KEY")
rerank_model = os.getenv("RERANK_MODEL")

def truncate_text(text: str, max_len: int=8192) -> str:
    """Returns truncated text if the length of text exceed max_len."""
    # return self.encoding.decode(self.encoding.encode(text)[:max_len])
    return text[:max_len]


async def get_embedding(query: Union[str, List[str]]):
    # 如果是字符串，则为query，直接处理
    if isinstance(query, str):
        responses = await embedding_client.embeddings.create(
            model=embedding_model,
            input=query,
            encoding_format="float",
            dimensions=embedding_dimensions
            )
        return responses.data[0].embedding
        
    # 批处理
    semaphore = asyncio.Semaphore(1)  # 限制并发数

    async def process_batch(batches):
        batches = [truncate_text(t, embedding_max_len) for t in batches]
        
        async with semaphore:
            responses = await embedding_client.embeddings.create(
                model=embedding_model,
                input=batches,
                encoding_format="float",
                dimensions=embedding_dimensions 
            )
            return [response.embedding for response in responses.data]

    # 将查询分成每组10条
    batches = [query[i:i + embedding_batch_size] for i in range(0, len(query), embedding_batch_size)]

    # 并发处理所有批次
    tasks = [process_batch(batch) for batch in batches]
    results = await asyncio.gather(*tasks)

    res = [embedding for batch_result in results for embedding in batch_result]
    # print(res)
    # print(len(res[0]))
    
    # 将所有结果合并
    return [embedding for batch_result in results for embedding in batch_result]


async def get_rerank(query: str, texts: list):
    if len(texts) == 0:
        return np.array([]), 0
    prefix = '<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be "yes" or "no".<|im_end|>\n<|im_start|>user\n'
    suffix = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
    instruction = (
            "Given a web search query, retrieve relevant passages that answer the query"
        )

    # query_template = "{prefix}<Instruct>: {instruction}\n<Query>: {query}\n"
    query_template = "<Instruct>: {instruction}\n<Query>: {query}\n"
    document_template = "<Document>: {doc}{suffix}"
    query = query_template.format(prefix=prefix, instruction=instruction, query=query)
    texts = [document_template.format(doc=doc, suffix=suffix) for doc in texts]

    headers = {
        "Content-Type": "application/json",
        "accept": "application/json",
        "Authorization": f"Bearer {rerank_key}"
    }
    
    truncated_texts = [truncate_text(t, rerank_max_len) for t in texts]

    data = {
        "model": rerank_model,
        "query": query,
        "documents": truncated_texts,
        # "truncate_prompt_tokens": 8192,
    }
    
    async with httpx.AsyncClient(timeout=3600) as client:
        resp = await client.post(
            os.getenv("RERANK_BASE_URL"),
            headers=headers,
            json=data
        )
        resp.raise_for_status()
        res = resp.json()

    print(res)
    
    # result = [
    #     {
    #         "index": item["index"],
    #         "score": item["relevance_score"]
    #     }
    #     for item in res["results"]
    # ]

    # rank = np.zeros(len(texts), dtype=float)
    # for d in res["results"]:
    #     rank[d["index"]] = d["relevance_score"]
    # print(result)
    # return result




from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any, Optional

class SearchModel(BaseModel):
    chunk_id: str = Field(..., description="ID")
    content: str = Field(..., description="文字内容、表格的html内容、图片表格的caption")
    summary: str = Field(default="", description="摘要")
    file_id: str = Field(..., description="文件ID")
    file_path: str = Field(..., description="文件路径")
    img_path: str = Field(..., description="图片路径")
    update_time: str = Field(..., description="更新时间")
    score: float = Field(..., description="chunk相似度分数")
    bbox_type: str = Field(default="text", description="边界框类型")
    bbox: List[Any] = Field(default_factory=list, description="边界框坐标")
    title: str = Field(default="", description="标题（图片、表格、文字）")
    page_idx: List[Any] = Field(default_factory=list, description="页码索引")
    others: str = Field(default="", description="其他扩展字段")
    
    
    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典格式（兼容原有代码）
        使用 model_dump() 方法，包含所有字段和额外字段
        """
        return self.model_dump(include=None, exclude_none=False)



async def main():
    b = [SearchModel(chunk_id='ap1000_7061d1d1c74c40fb9ef9365c273982af-594', content='表6.12 不同运行模式下设备冷却水系统参数', summary='表6.12 不同运行模式下设备冷却水系统参数', file_id='a6a18863-3cf5-42b3-9b60-335b29429ca2', file_path='/mnt/ddata2/cc007/MinerU-2.6.6/my_project/test_case/ap1000.pdf', img_path='/mnt/ddata2/cc007/MinerU-2.6.6/my_project/parser/mineru_output/ap1000/auto/images/b8a8f0e57017c9d122ced60ecc26caf90399cbfd8376df709addef4dcbd292fe.jpg', update_time='2025-12-19T13:47:34.694669', score=0.5913205146789551, bbox_type='table', bbox=[[105, 491, 912, 796]], title='6.4.5.4 换料', page_idx=[297], others=''), SearchModel(chunk_id='ap1000_b62069ca8e1146e78ef0e5e89174e458-577', content='设备冷却水系统是一个非安全相关的封闭回路的冷却水系统，它在电厂运行的各个阶段，包括停堆和事故之后，把那些可能含有放射性水的系统，如反应堆冷却剂系统、化容系统、余热排出系统，产生的热量排到厂用水系统。因此它在放射性系统和外界环境之间起到一个屏障的作用。\n设备冷却水系统执行如下非安全相关的纵深防御功能·在正常停堆、换料和半管运行时，为正常余热排出系统的热交换器及泵\n提供冷却。\n·为化学和容积控制系统补给泵的小流量热交换器提供冷却。\n·为乏燃料池热交换器提供冷却。\n其他非安全相关的功能包括：\n·提供放射性物质向环境泄漏的屏障。  \n·提供厂用水向一回路系统泄漏的屏障。  \n·为支持电厂正常运行所需的各种非安全相关设备提供冷却。  \n·在非能动余热排出热交换器运行时，向RNS 热交换器提供冷却水以冷却安全壳内置换料水箱的水。  \n·在非能动堆芯冷却系统缓解事故后的电厂恢复运行期间，向 RNS 系统提供冷却水带走堆芯热量。\n电厂停堆的第一阶段是将热量从反应堆冷却剂系统通过蒸汽发生器传递到主蒸汽系统。\n在冷停堆的第二阶段，CCS 与 RNS 一同将衰变热和显热从堆芯和反应堆冷却剂系统导出，降低反应堆冷却剂系统的温度。', summary='设备冷却水系统为多个非安全相关系统提供冷却，屏障放射性物质泄漏，支持停堆与事故后热量导出', file_id='a6a18863-3cf5-42b3-9b60-335b29429ca2', file_path='/mnt/ddata2/cc007/MinerU-2.6.6/my_project/test_case/ap1000.pdf', img_path='', update_time='2025-12-19T13:47:34.694669', score=0.5956043004989624, bbox_type='text', bbox=[[116, 775, 920, 878], [163, 885, 710, 906], [178, 913, 912, 934], [194, 99, 297, 119], [178, 125, 791, 147], [178, 154, 509, 175], [167, 184, 451, 203], [175, 209, 916, 395], [118, 402, 914, 451], [118, 456, 912, 506]], title='6.4.2 系统功能', page_idx=[288, 289], others=''), SearchModel(chunk_id='ap1000_51301d2e3db04eb5b8786169cb86fd41-234', content='反应堆冷却剂泵', summary='反应堆冷却剂泵', file_id='a6a18863-3cf5-42b3-9b60-335b29429ca2', file_path='/mnt/ddata2/cc007/MinerU-2.6.6/my_project/test_case/ap1000.pdf', img_path='/mnt/ddata2/cc007/MinerU-2.6.6/my_project/parser/mineru_output/ap1000/auto/images/f2331efa332de8ea2643edab4d9c35010405099951d6bd0b515575f83b348cc6.jpg', update_time='2025-12-19T13:47:34.694669', score=0.6023997664451599, bbox_type='table', bbox=[[110, 124, 910, 203]], title='表3.2 AP1000 RCS名义设计参数和运行参数', page_idx=[115], others=''), SearchModel(chunk_id='ap1000_c5bcc7d0409f4d43b0936011ff8a2125-585', content='设备冷却水系统的设备概述如下，各部件的位置参见图6.6,CCS各设备的额定设计参数参见表6.11。', summary='设备冷却水系统概述见图6.6和表6.11', file_id='a6a18863-3cf5-42b3-9b60-335b29429ca2', file_path='/mnt/ddata2/cc007/MinerU-2.6.6/my_project/test_case/ap1000.pdf', img_path='', update_time='2025-12-19T13:47:34.694669', score=0.6222241520881653, bbox_type='text', bbox=[[108, 677, 896, 719]], title='6.4.4 设备描述', page_idx=[292], others=''), SearchModel(chunk_id='ap1000_c0b83222d59548f4a5d331915cde7d67-587', content='设备冷却水系统有两台卧式离心泵，由交流电机驱动。泵的流量能够满足相应热交换器的换热热负荷要求。在电厂正常运行时只需一台泵就可以满足系统设计要求，另一台泵可以退出运行。但是在停堆冷却时，为达到设计的冷却速率，两台泵都要求运行，如果只运行一台冷却水泵就会延长停堆冷却时间。', summary='设备冷却水系统设两台离心泵，正常运行单泵即可，停堆冷却时需双泵运行以保证冷却速率', file_id='a6a18863-3cf5-42b3-9b60-335b29429ca2', file_path='/mnt/ddata2/cc007/MinerU-2.6.6/my_project/test_case/ap1000.pdf', img_path='', update_time='2025-12-19T13:47:34.694669', score=0.6098792552947998, bbox_type='text', bbox=[[112, 153, 910, 250]], title='6.4.4.2 设备冷却水泵', page_idx=[294], others='')]
    # import random
    # random.shuffle(a)  # 直接打乱原列表
    print(b)  # 输出随机顺序，如
    query = "设备冷却水系统"
    content_list = [zz.content for zz in b]
    # rerank_results = await get_rerank(query, content_list)
    rerank_results = [{'index': 3, 'score': 0.9999687671661377}, {'index': 4, 'score': 0.8943564224243}, {'index': 1, 'score': 0.7998379945755005}, {'index': 0, 'score': 0.697708201408386}, {'index': 2, 'score': 0.5919264554977417}]
    # print(rerank_results)
    # for items in rerank_results:
    #     idx = items['index']
    #     new_score = items['score']
    for idx, new_score in rerank_results:
        print(new_score)
        print(idx)
        # b[idx].score = float(new_score)
        
    b.sort(key=lambda x: x.score, reverse=True)
    # print(b) 

if __name__ == "__main__":
    # a = ['林诚格 主 编郁祖盛 副主编欧阳予 主 审', '图4.13 非能动余热排出热交换器', '在党中央、国务院的正确领导下，我国核电事业经过二十多年的发展，在核电发展的各个方面都取得了显著成绩。特别是近几年，国家结合国民经济发展、改善能源结构、保护环境的需要，制定了“积极推进核电建设”的战略方针，在以下方面做出了重大举措，使我国核电事业步入了快速发展的轨道。第一，在法律、法规、政策方面，国家营造了一个核电良好发展的法制环境；第二，国家颁布了《核电中长期发展规划(2005—2020年)》,首次明确了我国核电发展的目标；第三，国家明确了我国核电发展的技术路线，决定走引进、消化、吸收、再创新的道路，引进目前世界上最先进的第三代核电技术 AP1000,为形成具有自主知识产权的核电技术创造了条件；第四，国家在中长期科技发展规划中确立了大型先进压水堆和高温气冷堆重大专项，并已开始组织实施；第五，对核电发展体制进行了改革，成立了国家核电技术公司，授予了中国电力投资集团公司第三张核电业主牌照，核电业务纳入到国家能源局统一管理；第六，陆续批准并开工建设一批新的核电项目。\n国家核电技术公司正是在这种大背景下于2007年5月组建成立的。正如国务院副总理曾培炎同志在公司成立大会上指出的，组建国家核电技术公司，是实施国家能源发展战略的需要，是核电体制改革的重大突破，是尽快提高我国核电自主化能力、推进核电建设、加快能源结构调整的重大举措。国家也明确了，国家核电技术公司是经国务院授权，代表国家对外签约，受让第三代先进核电技术，实施相关工程设计和项目管理，通过消化、吸收、再创新形成中国核电技术品牌的主体，是实现第三代核电技术引进、工程建设和自主化发展的主要载体和研发平台，是大型先进压水堆重大专项的实施主体。\n非能动的第三代压水堆核电技术作为当前国际上最先进的核电技术，受到了核工业界各方的高度关注。为了促进各方全面了解非能动的第三代压水堆核电技术，国家核电技术公司组织核能领域的专家着手编写系统介绍非能动的第三代压水堆核电技术的书籍，这将有助于第三代核电技术在国内的应用、推广，有助于核电技术研发、工程设计、设备制造、工程建设、运行管理等方面人才的成长，有助于公众对核电技术的了解与参与，为我国核能事业的可持续发展提供支撑。希望通过本书，能为业界人士和相关人员提供有益的帮助，同时也加强国家核电技术公司与关心支持我国核电事业发展人士的联系与沟通，为共同推进我国核能事业的发展做贡献。', '热交换器入口管与入口封头相连接，入口封头和管板通过一个外伸法兰被固定在IRWST 的壁上。热交换器由一个固定在IRWST 上的框架所支承，框架与IRWST 的底板和天花板相连接。热交换器的支承按照ASMEⅢ NF分卷设计，为抗震I类设备。外伸法兰的设计可以适应热膨胀。热交换器出口管与置于入口封头垂直下方靠近箱子底部的出口封头相连接。出口封头的结构和入口封头一样。两个封头管板的结构都和蒸汽发生器管板类似，并且设有用于检查和维修的人孔。\n使产生碎片也不会流到再循环滤网。\n(4)在安全壳再循环滤网附近的表面不使用涂层，所指“表面”由本章4.3.6.3节“安全壳再循环滤网”中所定义。这些表面是由不需要涂层的材料制成。\n(5)IRWST 是封闭的，从而限制碎片进入IRWST 滤网。\n(6)安全壳再循环滤网要高于安全壳的最低位置。\n(7)在开始安全壳再循环以前要有一段较长的碎片沉积时间。\n(8)由于AP1000 没有采用安全相关的泵，因此安全相关的泵吸入空气的问题将不再出现。评估结果表明常规余热排出系统泵可以在IRWST 和安全壳的最低水位情况下运行。\n(9)电厂必须承诺，有相应的清洁程序来防止碎片进入安全壳。\n(10)限制通风过滤器材料和纤维制造的防火材料等的使用。因为这类材料都可能成为潜在纤维碎片的来源，这些材料只允许在不受假想喷射和水淹没以外的区域使用。', '图4.14(a) IRWST 滤网布置平面图', 'IRWST滤网(IRWST Screens)设置于IRWST 内底部。IRWST 有两个单独的滤网，分别位于水箱的两端，平面布置和竖直布置分别见图4.14(a) 和(b)。IR-WST与安全壳隔离，在电厂运行期间，其通风口和溢流口通常情况下是关闭的，这减少了杂质进入的潜在风险。电厂执行的“维修和检查运行清洁程序”可限制外来杂质进入水箱。技术规格书要求在每次停堆换料时对滤网进行目视检查。', '压水堆的安全壳(Containment) 通常是内径约 $4 0 \\mathrm { m }$ , 壁厚约 $1 \\mathrm { m }$ , 高约 $6 5 ^ { \\sim }$ 70m 的圆柱状或球形预应力混凝土大型建筑物，内设置有直径为 $1 0 \\mathrm { m }$ 的设备闸门和一个与辅助厂房联接的人员闸门，顶部设置有起吊能力为 $2 5 0 \\sim 3 0 0 \\mathrm { t }$ 的环形吊车。安全壳的作用是将一回路系统中带放射性物质的主要设备包容在一起，以防止放射性物质向外扩散；即使在核电厂发生最严重事故时，放射性物质仍能全部被封闭在安全壳内不致影响到周围环境。', 'AP1000 的安全壳与通常压水堆的预应力混凝土安全壳不同，他由两层组成，其内层为圆柱形钢制容器，外层为钢筋混凝土屏蔽构筑物，均属抗震I类构筑物：\n内层独立式的安全壳是带上下椭圆封头的圆柱形钢制容器，它也是整个非能动安全壳冷却系统的组成部分。安全壳钢制容器和非能动安全壳冷却系统的作用是，从安全壳移出足够的能量，保证在设计基准事故下，安全壳不会超压。\n在正常运行期间，屏蔽构筑物的作用是给安全壳钢制容器、带放射性的系统和部件提供保护性屏障，以免受外部事件(飓风、飞射物等)的影响。屏蔽构筑物的另外一个作用是作为非能动安全壳冷却系统的一个组成部分。', '表5.1 钢制安全壳压力容器的压力和温度的计算值', '钢制安全壳容器(Steel Containment Vessel)由五个主要结构模块组装建造而成(见图5.1)。每个模块都由预先成型的、喷好漆的钢板(SA738) 制成。这 些模块包含环形加强筋、环吊梁、设备闸门、人员气闸门、贯穿件和其他附件。安全壳的设计能支撑环吊及其载荷，并考虑了蒸汽发生器的更换。环吊是为了\n钢制安全壳容器是独立式的带上下椭圆封头的圆柱形钢制容器，按照ASME III NE分卷—MC级设备(金属安全壳材料)的要求设计制造。容器标高 $1 3 2 ^ { \\prime }$ ′-3”(40.31m)以上部分暴露在外部环境空气中，作为非能动安全壳冷却系统空气冷却流道的一部分。\n安全壳容器有如下设计特征：\n直径： $1 3 0 \\mathrm { f t } ( 3 9 . 6 2 4 \\mathrm { m } )$   \n高度：215 ft 加 $4 \\mathrm { i n } ( 6 5 . 6 3 4 \\mathrm { m } )$   \n设计标准：ASME II,Division 1  \n材料：SA738,B 级  \n设计压力： $5 9 \\mathrm { p s i g } ( 0 . 4 0 7 ~ \\mathrm { M P a } ,$ ,表压)  \n设计温度： $3 0 0 \\mathrm { F } ( 1 4 8 . 8 9 ^ { \\circ } \\mathrm { C } )$   \n设计外压：2.9 psig(0.20 bar,压差)\n表5.1列出了安全壳容器在事故情况下的压力温度峰值。', "安全壳容器中大部分圆柱体的厚度是 $1 . 7 5 \\mathrm { i n } ( 4 4 . 4 5 \\ \\mathrm { \\quad m m } )$ 。最底层的安全壳容器圆柱形外壳的厚度增加到 $1 . 8 7 5 \\mathrm { i n } ( 4 7 . 6 2 \\mathrm { m m } )$ , 从而为被埋置的过渡区域提供腐蚀余量。封头厚度为 $1 . 6 2 5 \\mathrm { i n } ( 4 1 . 2 7 \\mathrm { m m } )$ 。 封头是长径为130 ft$( 3 9 . 6 2 4 \\mathrm { m } )$ 、 高度为37ft7.5in(11.468 m)的椭球体。\n设置两个设备闸门， 一个安装在运行平台标高为 $1 3 5 ^ { \\prime } { - } 3 ^ { \\prime }$ (41.22m) 处，内径为16 ft(4.877m)。 另一个在标高为107'-2”(32.66m) 处可允许不同等级的设 备进入安全壳，它的内径为16 ft(4.877m)。\n设置两个人行通道气闸。每个都与其各自的设备闸门相邻近。每个人行通道气闸的外径大约为10ft(3.048m)以容纳一个开口达到3'-6”宽(1.067m),", '化学添加箱(Chemical Addition Tank)是一个小型、立式圆柱箱体，用来投入过氧化氢溶液(及/或其他除藻剂)以防止储水箱和辅助水箱中藻类滋生。', '储水箱再循环管路中设有两台离心再循环泵(RecirculationPumps)。这两 台泵的容量设计考虑在一台泵运行时可将水箱中的水装量每周循环一次。两台泵均可手动接入，从辅助水箱取水，每台泵都能够向水箱或直接向安全壳，并同时向乏燃料池提供用水。两台泵可以手动接入并联运行以满足消防系统用水需求。', '表5.3 非能动安全壳冷却系统设备性能参数', '续表', '再循环加热器(Recirculation Heater)用于防止水冻结，其设计加热容量考虑箱体和再循环管道在最低厂址温度下的热损失。\n非能动安全壳冷却系统设备性能参数见表5.3。', '正常运行工况下，空气从屏蔽构筑物顶部入口进入，流过下降流道后又反向流过上升流道，带走安全壳容器壁传递的热量，最后从烟囱排至环境。\n正常运行时通过运行2台再循环泵中的1台，利用再循环管路对非能动安全壳冷却水储水箱水装量进行循环。再循环管路设有一台加热器，自动启动以维持水箱的水温在最低整定值以上。水箱及辅助水箱定期取样并通过再循环管路提供的化学添加箱加入除藻剂。水箱及辅助水箱设置水位监测，在达到最低水位整定值时报警。补充去离子水以维持水箱水位在正常水位运行段。储水箱和辅助水箱均设有一个常开的溢水管以防止满溢。\n电厂正常运行期间，非能动安全壳冷却系统的其他运行为：辅助水箱加热器自动启动维持水装量在最低温度整定值以上；监测阀门间温度，自动投入暖通空调系统以确保房间及其内部的系统管道、阀门温度高于最低房间温度整定值；监测水箱出口隔离阀可能的泄漏。\n在电厂正常运行期间， 一个气动供水隔离阀的误开将引发洒向安全壳钢制壳体外表面的水流。这类误动作可通过操纵员在主控室关闭串联的电动隔离阀来终止。电厂运行不会受到误动作的影响。误动作后大部分洒向安全壳壳体的水会沿安全壳容器壁向下流，汇流至安全壳内环廊底部的地漏。多重的环廊地漏将积水引出安全壳/屏蔽构筑物的环廊。环廊地漏布置在屏蔽构筑物墙内略高于楼板平面，将地漏被碎片堵塞的可能性减至最低。地漏常开(不设隔离阀)且每个地漏的大小足以接收非能动安全壳冷却系统的最大流量。', '图5.9 主蒸汽管双端断裂后安全壳内温度 $1 0 1 \\%$ 满功率)', '接到安全壳高-2压力信号后，非能动安全壳冷却系统的事故后运行自动启动。由于冷却空气流道常开，只要开启三个常关隔离阀中的任意一个，不需要其他动作即可启动系统，即启动事故后排热功能。非能动安全壳冷却系统亦可由操纵员在主控室或远程停堆工作站手动启动。系统的启动包括开启常关的水箱隔离阀。储水箱中的水流向钢制安全壳壳体外表面的顶部。水流由重力提供，分配至安全壳壳体外表面，并在安全壳容器的穹顶和壁面形成水膜。隔', '图5.10 AP1000 承受外部压力的分析', '在某些情况下安全壳会承受外部压力。例如，在严冬环境条件下失去全部交流电源时，会使安全壳承受最严重的外部压力载荷。由于断电使反应堆冷却系统和其他能动部件施加在安全壳内的热载荷减少，导致安全壳内大气温度下降，随之压力也下降。假定环境温度是一 $\\cdot 4 . 4 \\mathrm { ^ { \\circ } C }$ ,稳定风速以 $\\mathrm { 4 8 m i l e / h ( 2 1 . 5 m / \\Delta \\mathrm { s } ) }$ 吹过和冷却安全壳容器。保守假设安全壳内初始条件为：温度 $4 9 ^ { \\circ } \\mathrm { C }$ 、压力为负0.2 psig(0.0014MPa) 和 $1 0 0 \\%$ 相对湿度。用WGOTHIC 程序算得一小时后安全壳承受外压压差2.9 psid(0.02 MPa)。其压力变化曲线见图5.10。操纵员应有足够的时间来防止安全壳的外压压差大于设计值。', '表6.9 AP1000 设备冷却水系统与先进的改良型压水堆 的安全相关冷却水系统主要设备及数量的比较', 'AP1000 的设备冷却水系统(Component Cooling Water System,CCS)与先 进的改良型压水堆的安全相关冷却水系统相比，设计简化。两种设计的主要设备其数量的比较见表6.9。\nAP1000 简化的设备冷却水系统(CCS) 和系统中使用的非安全相关的设备明显地降低了核电厂的建造成本和运行成本。', '设备冷却水系统是一个非安全相关的封闭回路的冷却水系统，它在电厂运行的各个阶段，包括停堆和事故之后，把那些可能含有放射性水的系统，如反应堆冷却剂系统、化容系统、余热排出系统，产生的热量排到厂用水系统。因此它在放射性系统和外界环境之间起到一个屏障的作用。\n设备冷却水系统执行如下非安全相关的纵深防御功能·在正常停堆、换料和半管运行时，为正常余热排出系统的热交换器及泵']
    # asyncio.run(get_embedding(["大模型","gaga"]))
    # asyncio.run(get_embedding(a))
    
    # asyncio.run(get_rerank('今天天气怎么样',['中国的首都是北京','今日晴转多云']))
    # asyncio.run(get_rerank('Milvus 支持哪些检索方式？',['Milvus 是一个向量数据库，主要用于高维向量的相似度搜索。','Milvus 支持向量检索、标量过滤以及混合检索等多种查询方式。', 'Milvus 的部署方式包括单机版和分布式集群。', '向量数据库常用于推荐系统和语义搜索。']))
    # query1 = "What is the capital of China?"
    # query2 = "如何在 Milvus 中实现混合检索？"
    # documents = [
    #     "The capital of China is Beijing.",
    #     "Milvus 是一个高性能向量数据库。",
    # ]
    
    query3 = "信息科电话是多少"
    documents=[
"科室名称:客服与投诉中心",
"科室代码：10086,科室名称：信息中心本级",
"科室代码：10086,科室名称：客服与投诉中心",
"科室：机房，电话号码：8888888811；短号：00909090",
"科室名称：信息中心本级",
"科室：信息中心值班，考勤单元：信息中心；电话号码：13131313131313；短号：090909090；上级科室：行政后勤",
"科室：信息中心办公室，考勤单元：信息中心；电话号码：13131313131313；短号：090909090；上级科室：行政后勤",
"科室：信息技术中心（值班），考勤单元：信息中心；电话号码：13131313131313；短号：090909090；上级科室：行政后勤"
]
    # # asyncio.run(get_rerank('如何在 Milvus 中实现混合检索？',['混合检索通常指结合向量相似度与关键词搜索。','Milvus 的混合检索可以通过 dense vector 和 sparse vector 共同完成。', '检索系统中常见的优化方法包括缓存和并发控制。', 'Milvus 是一个高性能向量数据库。']))
    # asyncio.run(get_rerank('如何在 Milvus 中实现混合检索？',documents))
    asyncio.run(get_rerank(query3,documents))
    # asyncio.run(get_rerank('What is the capital of France?',['The capital of Brazil is Brasilia.','The capital of France is Paris.','Horses and cows are both animals']))
    # asyncio.run(main())
    
    
    # def rerank_score(query, documents):
    #     import requests
    #     import json
    #     url = "http://127.0.0.1:30000/v1/rerank"
    #     headers = {
    #         "Content-Type": "application/json"
    #     }
    #     query_prefix = "<|im_start|>system\nJudge whether the Document meets the requirements based on the Query and the Instruct provided. Note that the answer can only be \"yes\" or \"no\".<|im_end|>\n<|im_start|>user\n"
    #     document_suffix = "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
    #     instruction = "Given a web search query, retrieve relevant passages that answer the query.\n"
    #     q = f'{query_prefix} <Instruct>: {instruction} <Query>: {query}\n'
    #     d = [f'<Document>: {document} {document_suffix}' for document in documents]
    #     data = {
    #         "query": q,
    #         "documents": d
    #     }
    #     response = requests.post(url, headers=headers, data=json.dumps(data))
    #     # print(response.text)
    #     j = response.json()
    #     return j
    
    
    # print(rerank_score(query2, documents))
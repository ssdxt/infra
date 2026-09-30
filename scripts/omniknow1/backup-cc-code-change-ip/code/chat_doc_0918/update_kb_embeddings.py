import os
import sys
sys.path.append(".")
from tqdm import tqdm
from server.knowledge_base.kb_api import UpdateEmbeddingParams, update_embedding

# KB_ROOT_PATH = "/mnt/ddata/zzj/chat_doc_1.2/knowledge_base"
KB_ROOT_PATH = "/mnt/ddata/zzj/chat_doc_1.1test/knowledge_base"
# KB_ROOT_PATH = "/mnt/ddata/zzj/chat_doc_1.2/knowledge_test"

def update_all_kb_embeddings():
    """
    更新所有知识库的向量存储
    """
    kb_folders = []
    error_list = [] 
    success_length = 0
    success_list = []
    for folder_name in os.listdir(KB_ROOT_PATH):
        folder_path = os.path.join(KB_ROOT_PATH, folder_name)
        if os.path.isdir(folder_path):
            kb_folders.append(folder_name)
    
    if not kb_folders:
        print(f"在 {KB_ROOT_PATH} 下未找到任何知识库文件夹")
        return
    
    print(f"找到以下知识库文件夹: {kb_folders}")
    
    for kb_name in tqdm(kb_folders, desc="更新知识库进度"):
        vector_store_path = os.path.join(KB_ROOT_PATH, kb_name, "vector_store/bge-large-zh")

        if not os.path.exists(vector_store_path):
            print(f"知识库 {kb_name} 的向量存储路径 {vector_store_path} 不存在，跳过")
            continue
        
        print(f"正在更新知识库 {kb_name} 的向量存储...")
        
        params = UpdateEmbeddingParams(
            old_index_path=vector_store_path,
            new_index_path=vector_store_path,
            new_embeddings_name='123',
            batch_size=8
        )
        
        result = update_embedding(params)
        
        if result.code == 200:
            print(f"知识库 {kb_name} 更新成功: {result.msg}")
            success_length += 1
            success_list.append(kb_name)
        else:
            print(f"知识库 {kb_name} 更新失败: {result.msg}")
            error_list.append((kb_name, result.msg))

    if error_list:
        print("以下知识库更新失败:")
        for kb_name, error_msg in error_list:
            print(f"知识库 {kb_name} 更新失败: {error_msg}")
    
    print(f"成功更新 {success_length} 个知识库的向量存储。")
if __name__ == "__main__":

    update_all_kb_embeddings()

    # print(len(os.listdir("/mnt/ddata/zzj/chat_doc_1.2/knowledge_base")))
    # from langchain.vectorstores.faiss import FAISS
    # knowledge_bases = [
    #     "饿1饿2 ",
    #     "EEA12928F36949A68B317DBD00DE215Ajiang_超真云-将近",
    #     "第一个",
    #     "CAB42F765892474B90627737B0CB5BBAhelio_111",
    #     "D07EDBE8A3F64C8F942E950805CB452Cafju059_idyi+",
    #     "yy的测试知识库",
    #     "EEA12928F36949A68B317DBD00DE215Ajiang_超真云-将",
    #     "82C19D696F3D45089A0B2C349D6DB192rslq231_111",
    #     "8D0725CF35EF42018BBDE850E13A66B4twih706_2322",
    #     "3333",
    #     "12321",
    #     "炽橙超真云官网文档",
    #     "123213123",
    #     "D07EDBE8A3F64C8F942E950805CB452Cafju059_123",
    #     "啊嚓收到",
    #     "贾维斯",
    #     "王鑫111",
    #     "82C19D696F3D45089A0B2C349D6DB192rslq231_阿斯顿撒打算",
    #     "1232133123",
    #     "0FCE8D02F0CD4E0F80B10A73DDA5D0D9kddp614_培训助手",
    #     "87607C8383434BF49233716B5FB5B41Cupajhk_额头人与人",
    #     "12312321",
    #     "87607C8383434BF49233716B5FB5B41Cupajhk_企业技能培训",
    #     "123213",
    #     "FF3BB92F451445059A0F653B663C841Aljnf054_1",
    #     "0dc39660806811ee85c92344961a67f9czy_222",
    #     "MANUAL-1877888",
    #     "0dc39660806811ee85c92344961a67f9czy_111",
    #     "F021D25A8CAB4ACB8917AE48859A00C4admin_测试",
    #     "82C19D696F3D45089A0B2C349D6DB192rslq231_水电费1121232实打实大师",
    #     "tjb",
    #     "123213123cc",
    #     "333",
    #     "EEA12928F36949A68B317DBD00DE215Ajiang_超真云平台",
    #     "8D0725CF35EF42018BBDE850E13A66B4twih706_233",
    #     "111",
    #     "22222",
    #     "12",
    #     "8D0725CF35EF42018BBDE850E13A66B4twih706_23",
    #     "测试1111",
    #     "10D636A05FE4407998A9129C8E760CACqcrp474_金华创明电子商务有限公司",
    #     "66FFE7E2422F43F3A8CE425F083408D9flph353_zzjzzj",
    #     "D07EDBE8A3F64C8F942E950805CB452Cafju059_f",
    #     "21CE4D20DF8E404DAF52DF2D69DA02B2spring_智能助手",
    #     "啊实打实大苏打",
    #     "7A0AF8DBDAC746ED86E8CF1DA4903F12dongjian_123",
    #     "D07EDBE8A3F64C8F942E950805CB452Cafju059_12356735687338",
    #     "474489EC5AF240EDB4E5E010707EB3F3nheu796_123",
    #     "MANUAL-8543067983167705088",
    #     "CAB42F765892474B90627737B0CB5BBAhelio_12323",
    #     "MANUAL-8543069189884694528",
    #     "12345",
    #     "82C19D696F3D45089A0B2C349D6DB192rslq231_111111121232",
    #     "1234",
    #     "工号健康",
    #     "MANUAL-MANUAL-8536167352693104640",
    #     "33323",
    #     "D35BB3D019BD4CBCBAB408AEA976A628qurr930_ 是的方法",
    #     "啊啊啊",
    #     "8D0725CF35EF42018BBDE850E13A66B4twih706_2233",
    #     "213213",
    #     "21999E7EE20B4D079F110907EC91D5CAagga016_997543",
    #     "核电网站",
    #     "21999E7EE20B4D079F110907EC91D5CAagga016_555",
    #     "特种车辆底盘知识库",
    #     "0FCE8D02F0CD4E0F80B10A73DDA5D0D9kddp614_AAA",
    #     "1211",
    #     "613C2731493146BCAECAAD2713B26534cvmn658_11",
    #     "擦拭打赏",
    #     "FF3BB92F451445059A0F653B663C841Aljnf054_2",
    #     "wx_001",
    #     "2AFB0DFD9858478EAEA40BE8D09E4F7Ctvid281_yy的智能助手",
    #     "8D0725CF35EF42018BBDE850E13A66B4twih706_232",
    #     "MANUAL-8543067489138462720",
    #     "9A1CA859862D4D45BB4DA459F0F99C8Edouk277_机床故障维修",
    #     "MANUAL-8511259878190161920",
    #     "MANUAL-8536167352693105000",
    #     "222",
    #     "A9EEFDC7F2A640419D6531ECAED46495haji190_123",
    #     "工号监管环境 ",
    #     "82C19D696F3D45089A0B2C349D6DB192rslq231_水电费1121232",
    #     "12321312",
    #     "test",
    #     "大傻逼",
    #     "测试111",
    #     "cck",
    #     "21999E7EE20B4D079F110907EC91D5CAagga016_1",
    #     "cck4444",
    #     "21CE4D20DF8E404DAF52DF2D69DA02B2spring_企业知识库",
    #     "123",
    #     "8BBFF7D372264137BD8829047895A616mvpo175_喷印机操作使用说明",
    #     "这是一个知识库",
    #     "MANUAL-8551744072625704960",
    #     "F27117EF4A7A45FF866A403540C3F49Ekaum416_展会",
    #     "8BBFF7D372264137BD8829047895A616mvpo175_万事利丝绸喷印机操作使用说明",
    #     "王鑫app",
    #     "撒大苏打2312",
    #     "曾多次3123",
    #     "82C19D696F3D45089A0B2C349D6DB192rslq231_1111111",
    #     "测试app",
    #     "人工智能",
    #     "1"
    # ]

    # for kb_name in knowledge_bases:
    #     vector_store_path = os.path.join(KB_ROOT_PATH, kb_name, "vector_store/bge-large-zh")
    #     # if not os.path.exists(vector_store_path):
    #     #     print(f"知识库 {kb_name} 的向量存储路径 {vector_store_path} 不存在，跳过")
    #     #     continue
        
    #     old_faiss = FAISS.load_local(vector_store_path, "embeddings")

    #     if len(old_faiss.docstore._dict)!= 0:
    #         print(f"{kb_name}, 旧的向量库中共有 {len(old_faiss.docstore._dict)} 条数据")
        
        
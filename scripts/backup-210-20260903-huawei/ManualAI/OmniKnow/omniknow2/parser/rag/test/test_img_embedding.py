from transformers import AutoImageProcessor, AutoModel
import torch
from PIL import Image
import time
def main():
    # 加载模型
    model_path = "/mnt/ddata2/models/dinov3-vitl16-pretrain-lvd1689m"
    st = time.time()
    
    processor = AutoImageProcessor.from_pretrained(model_path)
    model = AutoModel.from_pretrained(model_path)
    device = torch.device('cuda:0' if torch.cuda.is_available() else "cpu")
    model.to(device)
    model.eval()
    st1 = time.time()
    print("加载模型时间:", st1 - st)
    ## 特征提取
    # image1 = Image.open('/mnt/ddata2/cc007/MinerU-2.6.6/my_project/output/0d477c61-e242-43bd-abcf-403eb44b2185/ap1000_test/auto/images/325b211945259420bc64c994724aab3aa92866261f58218dac2e289446daccf5.jpg')
    image2 = Image.open('/mnt/ddata2/user/zhouyufeng/docker/rustfs/data/public/Tesla/2024_model3/media/中控台总成 （（拆卸和更换））/GUID-B0372D5F-616F-4A49-B67C-916B764EB153-online-en-US.jpg')
    for i in range(1):
        st2 = time.time()
        with torch.no_grad():
            # inputs = processor(images=[image1,image2], return_tensors="pt").to(device)
            inputs = processor(images=image2, return_tensors="pt").to(device)
            print("inputs---------------------",inputs)
            # print("inputs---------------------",inputs["pixel_values"].shape)
            # print(processor)
            outputs = model(**inputs)
            pooled_output = outputs.pooler_output
            print(pooled_output)
            embedding = torch.nn.functional.normalize(pooled_output, p=2, dim=-1)
            print(embedding)
            print(embedding.shape)
            print(len(embedding))
            
            print(embedding.cpu().numpy().tolist())
            # print(len(embedding[0].cpu().numpy().tolist()))
        #     # print( pooled_output)
        #     # print(embedding[0])
        #     # print("Pooled output shape:", pooled_output.shape)
        # print("提取特征时间:", time.time() - st2)

if __name__ == '__main__':
    main()

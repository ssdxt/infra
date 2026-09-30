from PIL import Image
from PIL import ImageOps
import torch
from torchvision import transforms
from transformers import AutoModelForImageSegmentation


device = 'cuda' if torch.cuda.is_available() else 'cpu'
model = AutoModelForImageSegmentation.from_pretrained('/mnt/ddata2/cc007/rmbg-2.0', trust_remote_code=True).eval().to(device)


# Data settings
image_size = (1024, 1024)
output_size = (512,512)
transform_image = transforms.Compose([
    transforms.Resize(image_size),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
])

        # images = Image.open(query_img).convert("L")

image = Image.open("/mnt/ddata2/cc007/omniknow2/parser/rag/3DD77259-CF60-437E-A388-97B3F4051483.jpg")
# image = Image.open("/mnt/ddata2/cc007/omniknow2/parser/rag/IMG_2694.HEIC.JPG")
image = ImageOps.exif_transpose(image)
input_images = transform_image(image).unsqueeze(0).to(device)

# Prediction
with torch.no_grad():
    preds = model(input_images)[-1].sigmoid().cpu()
pred = preds[0].squeeze()
pred_pil = transforms.ToPILImage()(pred)
mask = pred_pil.resize(image.size)

mask = mask.resize(output_size)
image = image.resize(output_size)

image.putalpha(mask)

image.save("no_bg_image.png")

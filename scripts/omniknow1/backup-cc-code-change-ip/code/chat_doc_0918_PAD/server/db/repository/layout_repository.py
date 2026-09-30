import os
import cv2
import time
import logging
from PIL import Image
import numpy as np
from paddle.utils import try_import
from layout.predict_layout import YOLOLayoutPredictor
from layout.predict_system import TextSystem
from layout.predict_table import TableSystem
from layout.ppstructure.utility import cal_ocr_word_box
from layout.tools.infer.utility import args


def _check_image_file(path):
    img_end = {"jpg", "bmp", "png", "jpeg", "rgb", "tif", "tiff", "gif", "pdf"}
    return any([path.lower().endswith(e) for e in img_end])
    
def get_image_file_list(img_file, infer_list=None):
    imgs_lists = []
    if img_file is None or not os.path.exists(img_file):
        raise Exception("not found any img file in {}".format(img_file))

    if os.path.isfile(img_file) and _check_image_file(img_file):
        imgs_lists.append(img_file)
    elif os.path.isdir(img_file):
        for single_file in os.listdir(img_file):
            file_path = os.path.join(img_file, single_file)
            if os.path.isfile(file_path) and _check_image_file(file_path):
                imgs_lists.append(file_path)

    if len(imgs_lists) == 0:
        raise Exception("not found any img file in {}".format(img_file))
    imgs_lists = sorted(imgs_lists)
    return imgs_lists

def check_and_read(img_path):
    # 处理GIF文件
    if os.path.basename(img_path)[-3:].lower() == "gif":
        gif = cv2.VideoCapture(img_path)
        ret, frame = gif.read()
        if not ret:
            logger = logging.getLogger("ppocr")
            logger.info("Cannot read {}. This gif image maybe corrupted.")
            return None, False, False
        if len(frame.shape) == 2 or frame.shape[-1] == 1:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2RGB)
        imgvalue = frame[:, :, ::-1]
        return imgvalue, True, False
    # 处理PDF文件
    elif os.path.basename(img_path)[-3:].lower() == "pdf":
        fitz = try_import("fitz")

        imgs = []
        with fitz.open(img_path) as pdf:
            for pg in range(0, pdf.page_count):
                page = pdf[pg]
                mat = fitz.Matrix(2, 2)
                pm = page.get_pixmap(matrix=mat, alpha=False)

                # if width or height > 2000 pixels, don't enlarge the image
                if pm.width > 2000 or pm.height > 2000:
                    pm = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)

                img = Image.frombytes("RGB", [pm.width, pm.height], pm.samples)
                img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                imgs.append(img)
            return imgs, True, True
    # 处理常见图片格式（jpg, png, jpeg, bmp, webp等）
    else:
        img_suffix = os.path.basename(img_path).split('.')[-1].lower()
        if img_suffix in ['jpg', 'jpeg', 'png', 'bmp', 'webp', 'tif', 'tiff']:
            img = cv2.imread(img_path)
            if img is None:
                return None, False, False
            if len(img.shape) == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            elif img.shape[2] == 4:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            # 将单张图片放入列表中，以便与PDF处理保持一致的返回格式
            return [img], True, False
    
    # 如果不是支持的文件格式，返回None
    return None, False, False

def _predict_text(img,text_system):
        # text_system = TextSystem(args)
        return_word_box = args.return_word_box
        filter_boxes, filter_rec_res, ocr_time_dict = text_system(img)

        # remove style char,
        # when using the recognition model trained on the PubtabNet dataset,
        # it will recognize the text format in the table, such as <b>
        style_token = [
            "<strike>",
            "<strike>",
            "<sup>",
            "</sub>",
            "<b>",
            "</b>",
            "<sub>",
            "</sup>",
            "<overline>",
            "</overline>",
            "<underline>",
            "</underline>",
            "<i>",
            "</i>",
        ]
        res = []
        for box, rec_res in zip(filter_boxes, filter_rec_res):
            rec_str, rec_conf = rec_res[0], rec_res[1]
            for token in style_token:
                if token in rec_str:
                    rec_str = rec_str.replace(token, "")
            if return_word_box:
                word_box_content_list, word_box_list = cal_ocr_word_box(
                    rec_str, box, rec_res[2]
                )
                res.append(
                    {
                        "text": rec_str,
                        "confidence": float(rec_conf),
                        "text_region": box.tolist(),
                        "text_word": word_box_content_list,
                        "text_word_region": word_box_list,
                    }
                )
            else:
                res.append(
                    {
                        "text": rec_str,
                        "confidence": float(rec_conf),
                        "text_region": box.tolist(),
                    }
                )
        return res

def _has_intersection(rect1, rect2):
        x_min1, y_min1, x_max1, y_max1 = rect1
        x_min2, y_min2, x_max2, y_max2 = rect2
        if x_min1 > x_max2 or x_max1 < x_min2:
            return False
        if y_min1 > y_max2 or y_max1 < y_min2:
            return False
        return True

def _filter_text_res(text_res, bbox):
        res = []
        merged_text = ""
        merged_confidence = 0
        x_min, y_min, x_max, y_max = float('inf'), float('inf'), 0, 0

        for r in text_res:
            box = r["text_region"]
            rect = box[0][0], box[0][1], box[2][0], box[2][1]
            if _has_intersection(bbox, rect):
                res.append(r)
                merged_text += r["text"] + " "
                merged_confidence += r["confidence"]
                x_min = min(x_min, rect[0])
                y_min = min(y_min, rect[1])
                x_max = max(x_max, rect[2])
                y_max = max(y_max, rect[3])

        if len(res) > 0:
            merged_confidence /= len(res)
            # 确保合并后的文本区域有合理的大小
            if x_max > x_min and y_max > y_min:
                res = [{
                    "text": merged_text.strip(),
                    "confidence": merged_confidence,
                    "text_region": [[x_min, y_min], [x_max, y_min], [x_max, y_max], [x_min, y_max]],
                }]
            else:
                res = []  # 处理异常情况
        return res

# def run_ocr_model():
#     """
#     模型启动函数
#     """
#     layout_predictor = YOLOLayoutPredictor(args)
#     text_system = TextSystem(args)
#     table_system = TableSystem(args,text_system.text_detector,text_system.text_recognizer)

#     return layout_predictor,text_system,table_system


def analyze_layout(img,layout_predictor):
    """
    版面分析函数
    """
    layout_res = layout_predictor(img)

    return layout_res

def text_layout(img, img_idx,layout_predictor,text_system):
    """
    文字识别函数
    """
    ori_im = img.copy()
    layout_res = analyze_layout(img,layout_predictor)
    text_res = None

    if text_system is not None:
        text_res = _predict_text(img,text_system)
    else:
        h, w = ori_im.shape[:2]
        layout_res = [dict(bbox=None, label="table")]

    res_list = []
    for region in layout_res:
        res = ""
        if region["bbox"] is not None:
            x1, y1, x2, y2 = region["bbox"]
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        else:
            x1, y1, x2, y2 = 0, 0, w, h
        bbox = [x1, y1, x2, y2]

        if region["label"] in ["table", "figure"]:
            continue
                
        else:
            if text_res is not None:
                res = _filter_text_res(text_res, bbox)

        res_list.append(
            {
                "type": region["label"].lower(),
                "bbox": bbox,
                "res": res,
                "img_idx": img_idx+1,
                "score": region["score"],
            }
        )

    return res_list

def table_layout(img, return_ocr_result_in_table, img_idx, layout_res,table_system):
    """
    表格识别函数
    """
    ori_im = img.copy()

    res_list = []
    for region in layout_res:
        res = ""
        x1, y1, x2, y2 = region["bbox"]
        x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
        roi_img = ori_im[y1:y2, x1:x2, :]
        bbox = [x1, y1, x2, y2]

        if region["label"] == "table":
            if table_system is not None:
                res = table_system(roi_img, return_ocr_result_in_table)
                
        else:
            continue

        res_list.append(
            {
                "type": region["label"].lower(),
                "bbox": bbox,
                "res": res.get("html", ""),
                "img_idx": img_idx+1,
                "score": region["score"],
            }
        )

    return res_list
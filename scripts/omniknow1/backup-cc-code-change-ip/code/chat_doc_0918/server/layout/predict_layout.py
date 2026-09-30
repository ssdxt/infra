# Copyright (c) 2020 PaddlePaddle Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import os
import sys

__dir__ = os.path.dirname(os.path.abspath(__file__))
sys.path.append(__dir__)
sys.path.insert(0, os.path.abspath(os.path.join(__dir__, "../..")))

os.environ["FLAGS_allocator_strategy"] = "auto_growth"

import cv2
import numpy as np
import time

import server.layout.tools.infer.utility as utility
from server.layout.ppocr.data import create_operators, transform
from server.layout.ppocr.postprocess import build_post_process
from server.layout.ppocr.utils.logging import get_logger
from server.layout.ppocr.utils.utility import get_image_file_list, check_and_read
# from layout.ppstructure.utility import parse_args

logger = get_logger()

import torch
from ultralytics import YOLO

class YOLOLayoutPredictor:
    def __init__(self, args):
        # 加载你的 YOLOv8 模型
        self.model = YOLO(args.layout_model_dir)
        # 创建 class_id 到标签的映射
        self.class_id_to_label = {
            0: "header",
            1: "text",
            2: "reference",
            3: "figure_caption",
            4: "figure",
            5: "table_caption",
            6: "table",
            7: "title",
            8: "footer",
            9: "equation"
        }
    
    def __call__(self, img):
    
        # 使用 YOLOv8 模型进行推理
        results = self.model(img, conf=0.7)

        layout_res = []
        for result in results:
            for box in result.boxes:
                x1, y1, x2, y2 = box.xyxy[0]
                class_id = int(box.cls[0])
                score = float(box.conf[0])

                # 根据 class_id 映射到对应的标签
                label = self.class_id_to_label.get(class_id, "Unknown")

                layout_res.append({
                    "bbox": [x1, y1, x2, y2],
                    "label": label,
                    "score": score
                })

        # 返回与 LayoutPredictor 类一致的格式
        return layout_res

def main(args):
    image_file_list = get_image_file_list(args.image_dir)
    # layout_predictor = LayoutPredictor(args)
    layout_predictor = YOLOLayoutPredictor(args)
    count = 0
    total_time = 0

    repeats = 50
    for image_file in image_file_list:
        img, flag, _ = check_and_read(image_file)
        if not flag:
            img = cv2.imread(image_file)
        if img is None:
            logger.info("error in loading image:{}".format(image_file))
            continue

        layout_res, elapse = layout_predictor(img)

        logger.info("result: {}".format(layout_res))

        if count > 0:
            total_time += elapse
        count += 1
        logger.info("Predict time of {}: {}".format(image_file, elapse))


if __name__ == "__main__":
    main(parse_args())

import paddle
import numpy as np
from server.layout.tools.infer.utility import create_predictor, args
from ppocr.utils.logging import get_logger

logger = get_logger()

def test_model_loading():
    """测试模型加载和基本推理"""
    try:
        # 测试检测模型
        logger.info("Testing detection model...")
        det_predictor, det_input, det_output, det_config = create_predictor(None, "det", logger)
        logger.info(f"Detection model loaded successfully")
        
        # 测试识别模型
        logger.info("Testing recognition model...")
        rec_predictor, rec_input, rec_output, rec_config = create_predictor(None, "rec", logger)
        logger.info(f"Recognition model loaded successfully")
        
        # 测试表格模型
        logger.info("Testing table model...")
        table_predictor, table_input, table_output, table_config = create_predictor(None, "table", logger)
        logger.info(f"Table model loaded successfully")
        
        # 测试基本推理
        test_input = np.random.rand(1, 3, 640, 640).astype(np.float32)
        det_input.copy_from_cpu(test_input)
        det_predictor.run()
        
        logger.info("All models loaded and basic inference test passed")
        return True
        
    except Exception as e:
        logger.error(f"Model compatibility test failed: {e}")
        return False

if __name__ == "__main__":
    test_model_loading()

from server.layout.predict_layout import YOLOLayoutPredictor
from server.layout.predict_system import TextSystem
from server.layout.predict_table import TableSystem
from server.layout.tools.infer.utility import args

def run_ocr_model():
    """
    模型启动函数
    """
    layout_predictor = YOLOLayoutPredictor(args)
    text_system = TextSystem(args)
    table_system = TableSystem(args, text_system.text_detector, text_system.text_recognizer)
    
    return layout_predictor, text_system, table_system

layout_predictor, text_system, table_system = None,None,None
if not layout_predictor and not text_system and not table_system:
    layout_predictor, text_system, table_system = run_ocr_model()
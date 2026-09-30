# -*- coding: utf-8 -*-


import os
import click
#from melo.api import TTS
from api import TTS


    
    
@click.command()
@click.option('--ckpt_path', '-m', type=str, default="/deploy/models/melo/checkpoint.pth", help="Path to the checkpoint file")
@click.option('--text', '-t', type=str, default="123", help="Text to speak")
@click.option('--language', '-l', type=str, default="ZH", help="Language of the model")
@click.option('--output_dir', '-o', type=str, default="outputs", help="Path to the output")
def main(ckpt_path, text, language, output_dir):
    if ckpt_path is None:
        raise ValueError("The model_path must be specified")
    
    config_path = os.path.join(os.path.dirname(ckpt_path), 'config.json')
    model = TTS(language=language, config_path=config_path, ckpt_path=ckpt_path)
    
    for spk_name, spk_id in model.hps.data.spk2id.items():
        save_path = f'{output_dir}/{spk_name}/output.wav'
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        model.tts_to_file(text, spk_id, save_path)

if __name__ == "__main__":
    main()

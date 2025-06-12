import random
import logging
from pathlib import Path
from typing import Union


ROOT_PROMPT_DIR = "persona"


def get_prompt(filename: Union[str, Path]) -> str:
    """讀取並回傳指定檔案內容。"""
    try:
        with open(filename, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logging.error("Failed to load prompt from %s: %s", filename, e)
        return ""


def random_system_prompt(root: Union[str, Path] = ROOT_PROMPT_DIR) -> str:
    """隨機選取 persona 目錄下的提示詞。"""
    try:
        prompt_files = list(Path(root).glob("*.txt"))
        if not prompt_files:
            logging.warning("No prompt files found in %s", root)
            return ""
        filename = random.choice(prompt_files)
        logging.info("Random Select %s persona", filename.stem)
        return get_prompt(filename)
    except Exception as e:
        logging.error("Error selecting random prompt: %s", e)
        return "" 
import random
import logging
from pathlib import Path

def get_prompt(filename):
    """
    Reads and returns the content of a prompt file.
    
    Args:
        filename: Path to the prompt file.
        
    Returns:
        str: Content of the prompt file.
    """
    try:
        with open(filename, "r", encoding="utf-8") as file:
            prompt = file.read()
        return prompt
    except Exception as e:
        logging.error(f"Failed to load prompt from {filename}: {e}")
        return ""

def random_system_prompt(root="persona"):
    """
    Randomly selects and returns a system prompt from the specified directory.
    
    Args:
        root (str): Directory containing prompt files.
        
    Returns:
        str: Content of a randomly selected prompt file.
    """
    try:
        prompt_files = list(Path(root).glob('*.txt'))
        if not prompt_files:
            logging.warning(f"No prompt files found in {root}")
            return ""
            
        filename = random.choice(prompt_files)
        logging.info(f"Random Select {filename.stem} persona")
        return get_prompt(filename)
    except Exception as e:
        logging.error(f"Error selecting random prompt: {e}")
        return ""

from importlib import import_module
from pathlib import Path
from discord import app_commands

# 掃描 commands 目錄下的所有 .py 檔案，
# 自動收集其中的 app_commands.Command 物件，
# 方便集中註冊到 Bot。

THIS_DIR = Path(__file__).parent
ALL_COMMANDS: list[app_commands.Command] = []

for py_file in THIS_DIR.glob("*.py"):
    if py_file.name == "__init__.py":
        continue
    module_name = f"{__name__}.{py_file.stem}"
    module = import_module(module_name)
    for attr in vars(module).values():
        if isinstance(attr, app_commands.Command):
            ALL_COMMANDS.append(attr)


def register_commands(bot):
    """將 ALL_COMMANDS 註冊到給定的 Bot CommandTree。"""
    for cmd in ALL_COMMANDS:
        bot.tree.add_command(cmd) 
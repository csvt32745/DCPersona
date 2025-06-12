import pathlib, sys, os
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from utils.config_loader import load_config
from utils.logger import setup_logger
from schemas.agent_types import OverallState, MsgNode


def test_load_config():
    cfg = load_config("config.yaml")
    assert isinstance(cfg, dict)
    # 至少包含 agent 或 prompt_system 任一 key
    assert any(k in cfg for k in ("agent", "prompt_system"))


def test_logger_setup(capsys):
    setup_logger({"log_level": "INFO"})
    # 無例外即視為成功
    assert True


def test_overall_state():
    state = OverallState()
    assert state.tool_round == 0
    assert state.messages == []
    assert state.finished is False


def test_msgnode():
    msg = MsgNode(role="user", content="hello")
    assert msg.role == "user"
    assert msg.content == "hello" 
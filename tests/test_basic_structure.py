import pathlib, sys, os
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from utils.config_loader import load_typed_config
from utils.logger import setup_logger
from schemas.agent_types import OverallState, MsgNode
from schemas.config_types import AppConfig


def test_load_config():
    cfg = load_typed_config("config.yaml")
    assert isinstance(cfg, AppConfig)
    # 檢查必要的配置屬性
    assert hasattr(cfg, 'agent')
    assert hasattr(cfg, 'gemini_api_key')


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
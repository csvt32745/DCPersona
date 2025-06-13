import pathlib, sys, os
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from utils.config_loader import load_typed_config
from utils.logger import setup_logger
from schemas.agent_types import OverallState, MsgNode
from schemas.config_types import AppConfig, SystemConfig


def test_load_config():
    cfg = load_typed_config("config.yaml")
    assert isinstance(cfg, AppConfig)
    # 檢查必要的配置屬性
    assert hasattr(cfg, 'agent')
    assert hasattr(cfg, 'gemini_api_key')


def test_logger_setup(capsys):
    # 創建一個模擬的 AppConfig 物件
    mock_system_config = SystemConfig(log_level="INFO")
    mock_app_config = AppConfig(system=mock_system_config)

    setup_logger(mock_app_config)
    
    # 捕獲日誌輸出
    captured = capsys.readouterr()
    assert "Logger initialized" in captured.out or "Logger initialized" in captured.err
    assert "INFO" in captured.out or "INFO" in captured.err
    
    # 再次設置為預設，避免影響其他測試
    setup_logger(AppConfig())


def test_overall_state():
    state = OverallState()
    assert state.tool_round == 0
    assert state.messages == []
    assert state.finished is False


def test_msgnode():
    msg = MsgNode(role="user", content="hello")
    assert msg.role == "user"
    assert msg.content == "hello" 
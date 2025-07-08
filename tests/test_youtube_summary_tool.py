import sys, os, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
import types
from utils.youtube_utils import extract_first_youtube_url
from tools.youtube_summary import YouTubeSummaryTool

class FakeResponse:
    def __init__(self, text):
        self.text = text

class _FakeModels:
    def __init__(self):
        self.call_args = None
    def generate_content(self, model, contents, config):
        # 簡易回傳固定文字，並存參數供斷言
        self.call_args = (model, contents, config)
        return FakeResponse("這是一段摘要")

class FakeGoogleClient:
    def __init__(self):
        self.models = _FakeModels()

def _build_fake_config():
    ta_conf = types.SimpleNamespace(model="dummy-model", temperature=0.0, max_output_tokens=128)
    llm_ns = types.SimpleNamespace(models={"tool_analysis": ta_conf})
    config = types.SimpleNamespace(llm=llm_ns)
    return config


def test_extract_first_youtube_url():
    cases = [
        "請幫我總結 https://www.youtube.com/watch?v=pmNP54vTlxg 謝謝",
        "連結 https://youtu.be/pmNP54vTlxg?si=XXX",
        "跳到60秒 https://youtu.be/pmNP54vTlxg?si=XXX&t=60 其餘文字",
        "嵌入 https://www.youtube.com/embed/pmNP54vTlxg?rel=0",
        "https://youtu.be/ConMAwL-cmk?si=2a1iXnXe4BNOcQy-\n這影片在講啥",
    ]
    answers = [
        "https://youtu.be/pmNP54vTlxg",
        "https://youtu.be/pmNP54vTlxg",
        "https://youtu.be/pmNP54vTlxg",
        "https://youtu.be/pmNP54vTlxg",
        "https://youtu.be/ConMAwL-cmk",
    ]
    for text, answer in zip(cases, answers):
        url = extract_first_youtube_url(text)
        assert url == answer


def test_youtube_summary_tool_success():
    fake_client = FakeGoogleClient()
    config = _build_fake_config()

    tool = YouTubeSummaryTool(google_client=fake_client, config=config)
    result = tool._run("https://youtu.be/abcdefghijk")

    assert result.success is True
    assert "摘要" in result.message or result.message == "這是一段摘要"
    # 確認 Google API 有被呼叫
    assert fake_client.models.call_args is not None 
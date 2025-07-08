import sys, pathlib, types
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from tools.youtube_summary import YouTubeSummaryTool

class DummyModels:
    def __init__(self):
        self.calls = 0
    def generate_content(self, model, contents, config):
        self.calls += 1
        class R: text = "SUMMARY"
        return R()

class DummyClient:
    def __init__(self):
        self.models = DummyModels()

def _fake_cfg():
    ta_conf = types.SimpleNamespace(model="dummy", temperature=0.0, max_output_tokens=64)
    llm = types.SimpleNamespace(models={"tool_analysis": ta_conf})
    return types.SimpleNamespace(llm=llm)

def test_summary_cache_hit(monkeypatch):
    client = DummyClient()
    tool = YouTubeSummaryTool(google_client=client, config=_fake_cfg())
    url = "https://youtu.be/abcdefghijk"

    res1 = tool._run(url)
    assert res1.success and client.models.calls == 1

    # second call -> should use cache
    res2 = tool._run(url)
    assert res2.success and client.models.calls == 1
    assert res2.message == res1.message


def test_cache_persist_across_instances(monkeypatch):
    client = DummyClient()
    tool1 = YouTubeSummaryTool(google_client=client, config=_fake_cfg())
    url = "https://youtu.be/zzzzzzzzzzz"

    # first run (store)
    tool1._run(url)
    assert client.models.calls == 1

    # new instance should still see cache
    tool2 = YouTubeSummaryTool(google_client=client, config=_fake_cfg())
    tool2._run(url)
    assert client.models.calls == 1  # no extra API call


def test_cache_ttl_cleanup(monkeypatch):
    client = DummyClient()
    tool = YouTubeSummaryTool(google_client=client, config=_fake_cfg())
    url = "https://youtu.be/yyyyyyyyyyy"

    # mock time to control TTL
    import time as real_time
    base = real_time.time()
    monkeypatch.setattr(real_time, "time", lambda: base)
    tool._run(url)
    assert client.models.calls == 1  # stored

    # advance less than TTL (1h)
    monkeypatch.setattr(real_time, "time", lambda: base + 3600)
    tool._run(url)
    assert client.models.calls == 1  # cache hit

    # advance beyond TTL (25h)
    monkeypatch.setattr(real_time, "time", lambda: base + 60*60*25)
    tool._run(url)
    assert client.models.calls == 2  # new API call after cleanup 
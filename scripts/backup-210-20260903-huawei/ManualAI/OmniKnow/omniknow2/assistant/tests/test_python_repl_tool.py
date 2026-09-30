import sys
from types import SimpleNamespace

from src.tools.python_repl import _prepare_python_repl_code, python_repl_tool


class FakeRepl:
    def __init__(self) -> None:
        self.last_code = ""

    def run(self, code: str) -> str:
        self.last_code = code
        return "ok"


def test_prepare_python_repl_code_includes_remote_url_patch():
    prepared = _prepare_python_repl_code("result = _omniknow_encode_remote_url(raw_url)")

    assert "_omniknow_encode_remote_url" in prepared
    assert "_omniknow_pd.read_excel" in prepared
    assert prepared.rstrip().endswith("result = _omniknow_encode_remote_url(raw_url)")


def test_python_repl_bootstrap_encodes_non_ascii_http_paths():
    namespace: dict[str, object] = {}
    raw_url = (
        "http://omni-oss.czy3d.com:8371/57b39ed8-0283-4cb1-9990-257b1bfa5cc4/"
        "重卡维修专业知识库/documents/source/重卡技术性能表.xlsx"
    )
    prepared = _prepare_python_repl_code(
        f"encoded_url = _omniknow_encode_remote_url({raw_url!r})"
    )

    exec(prepared, namespace)

    encoded_url = namespace["encoded_url"]
    assert isinstance(encoded_url, str)
    assert "%E9%87%8D%E5%8D%A1" in encoded_url
    assert encoded_url.endswith(
        "%E9%87%8D%E5%8D%A1%E6%8A%80%E6%9C%AF%E6%80%A7%E8%83%BD%E8%A1%A8.xlsx"
    )


def test_python_repl_bootstrap_patch_survives_repeated_exec():
    prepared = _prepare_python_repl_code("pass")
    calls: list[str] = []

    def fake_original(value, *args, **kwargs):
        calls.append(value)
        return ("ok", value)

    fake_pandas = SimpleNamespace(
        read_excel=fake_original,
        read_csv=fake_original,
        ExcelFile=fake_original,
    )
    original_pandas = sys.modules.get("pandas")
    sys.modules["pandas"] = fake_pandas
    try:
        namespace: dict[str, object] = {}
        exec(prepared, namespace)

        wrapped = fake_pandas.read_excel
        wrapped.__globals__.pop("_omniknow_patch_io_target", None)
        wrapped.__globals__.pop("_omniknow_encode_remote_url", None)

        result = wrapped("http://example.com/重卡技术性能表.xlsx")
    finally:
        if original_pandas is not None:
            sys.modules["pandas"] = original_pandas
        else:
            del sys.modules["pandas"]

    assert result[0] == "ok"
    assert calls
    assert "%E9%87%8D%E5%8D%A1" in result[1]


def test_python_repl_bootstrap_patch_survives_missing_urllib_globals():
    prepared = _prepare_python_repl_code("pass")
    calls: list[str] = []

    def fake_original(value, *args, **kwargs):
        calls.append(value)
        return ("ok", value)

    fake_pandas = SimpleNamespace(
        read_excel=fake_original,
        read_csv=fake_original,
        ExcelFile=fake_original,
    )
    original_pandas = sys.modules.get("pandas")
    sys.modules["pandas"] = fake_pandas
    try:
        namespace: dict[str, object] = {}
        exec(prepared, namespace)

        wrapped = fake_pandas.ExcelFile
        for symbol in ("quote", "unquote", "urlsplit", "urlunsplit"):
            wrapped.__globals__.pop(symbol, None)

        result = wrapped("http://example.com/重卡技术性能表.xlsx")
    finally:
        if original_pandas is not None:
            sys.modules["pandas"] = original_pandas
        else:
            del sys.modules["pandas"]

    assert result[0] == "ok"
    assert calls
    assert "%E9%87%8D%E5%8D%A1" in result[1]


def test_python_repl_tool_prepends_bootstrap_before_running(monkeypatch):
    fake_repl = FakeRepl()

    monkeypatch.setattr("src.tools.python_repl.repl", fake_repl)
    monkeypatch.setattr("src.tools.python_repl._is_python_repl_enabled", lambda: True)

    result = python_repl_tool.invoke({"code": "print('ready')"})

    assert "Successfully executed" in result
    assert "_omniknow_encode_remote_url" in fake_repl.last_code
    assert fake_repl.last_code.rstrip().endswith("print('ready')")

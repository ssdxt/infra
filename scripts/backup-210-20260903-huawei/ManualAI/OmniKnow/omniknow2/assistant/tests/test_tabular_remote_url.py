from pathlib import Path
from types import SimpleNamespace

from parser.tabular.service import TabularParser
from parser.tabular.utils import encode_remote_file_url


class FakeReader:
    def __init__(self) -> None:
        self.validated_path: Path | None = None
        self.loaded_path: Path | None = None

    def validate_file_path(self, file_path: Path) -> None:
        self.validated_path = file_path

    def load_sheets(self, file_path: Path):
        self.loaded_path = file_path
        return [("sheet1", [["参数名", "值"], ["整备质量", "12000"]])]


class FakeProcessor:
    def build_sheet_artifacts(self, source_path: Path, raw_sheets):
        return [SimpleNamespace(table_name="truck_specs")]


class FakeWriter:
    def __init__(self) -> None:
        self.export_base_name = ""

    def write_outputs(self, output_dir: Path, sql_path: Path, export_base_name: str, artifacts):
        self.export_base_name = export_base_name
        return [output_dir / "truck_specs.csv"]


def test_encode_remote_file_url_percent_encodes_non_ascii_segments():
    raw_url = (
        "http://omni-oss.czy3d.com:8371/57b39ed8-0283-4cb1-9990-257b1bfa5cc4/"
        "重卡维修专业知识库/documents/source/重卡技术性能表.xlsx"
    )

    encoded_url = encode_remote_file_url(raw_url)

    assert "%E9%87%8D%E5%8D%A1" in encoded_url
    assert encoded_url.endswith(
        "%E9%87%8D%E5%8D%A1%E6%8A%80%E6%9C%AF%E6%80%A7%E8%83%BD%E8%A1%A8.xlsx"
    )


def test_tabular_parser_downloads_remote_file_and_keeps_original_name(tmp_path, monkeypatch):
    downloaded_path = tmp_path / "tabular_remote.xlsx"
    downloaded_path.write_bytes(b"placeholder")

    reader = FakeReader()
    writer = FakeWriter()
    parser = TabularParser(
        reader=reader,
        processor=FakeProcessor(),
        writer=writer,
    )

    monkeypatch.setattr("parser.tabular.service.is_remote_file_url", lambda _: True)
    monkeypatch.setattr(
        "parser.tabular.service.get_file_display_name",
        lambda _: "重卡技术性能表.xlsx",
    )
    monkeypatch.setattr(
        "parser.tabular.service.download_remote_file",
        lambda source, download_dir: downloaded_path,
    )

    response = parser.parse(
        file_id="file-1",
        file_path="http://example.com/重卡技术性能表.xlsx",
        output_dir=str(tmp_path / "artifacts"),
    )

    assert response.success is True
    assert reader.validated_path == downloaded_path
    assert reader.loaded_path == downloaded_path
    assert writer.export_base_name == "重卡技术性能表"
    assert downloaded_path.exists() is False

from types import SimpleNamespace

import pytest

from aperag.docparser import utils


def test_doc_conversion_normalizes_format_and_checks_result(tmp_path, monkeypatch):
    source = tmp_path / "legacy.doc"
    source.write_bytes(b"original")
    output = tmp_path / "converted"
    calls = []
    monkeypatch.setattr(utils, "get_soffice_cmd", lambda: "soffice")

    def convert(cmd, **kwargs):
        calls.append((cmd, kwargs))
        assert cmd[cmd.index("--convert-to") + 1] == "docx"
        (output / "legacy.docx").write_bytes(b"converted")
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

    monkeypatch.setattr(utils.subprocess, "run", convert)
    assert utils.convert_office_doc(source, output, ".docx") == output / "legacy.docx"
    assert source.read_bytes() == b"original"
    assert calls[0][1]["timeout"] > 0
    assert any(x.startswith("-env:UserInstallation=file:") for x in calls[0][0])


def test_doc_conversion_rejects_missing_input(tmp_path, monkeypatch):
    monkeypatch.setattr(utils, "get_soffice_cmd", lambda: "soffice")
    monkeypatch.setattr(utils.subprocess, "run", lambda *a, **kw: pytest.fail("must not start conversion"))
    with pytest.raises(FileNotFoundError):
        utils.convert_office_doc(tmp_path / "missing.doc", tmp_path, "docx")


def test_doc_conversion_rejects_success_without_output(tmp_path, monkeypatch):
    source = tmp_path / "legacy.doc"
    source.write_bytes(b"original")
    monkeypatch.setattr(utils, "get_soffice_cmd", lambda: "soffice")
    monkeypatch.setattr(utils.subprocess, "run", lambda *a, **kw: SimpleNamespace(returncode=0, stdout=b"", stderr=b""))
    with pytest.raises(RuntimeError, match="output"):
        utils.convert_office_doc(source, tmp_path / "out", "docx")

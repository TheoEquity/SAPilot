from aperag.service.sap_tcode import _purpose_overlap, _purpose_terms, extract_tcode_rows, match_exact_tcode


def test_tcode_rows_preserve_source_and_exclude_other_sap_identifiers():
    markdown = """
## 物料管理

|  |  |  |
| --- | --- | --- |
| **T-Code** | **功能描述** | **备注** |
| ME23N | 显示**采购订单** | 采购 |
| ME2N | 查询采购订单 | 清单 |

| 移动类型 | 描述 |
| --- | --- |
| 101 | 采购订单收货 |
"""
    rows = extract_tcode_rows(markdown)
    assert [(row.code, row.purpose, row.section) for row in rows] == [
        ("ME23N", "显示采购订单", "物料管理"),
        ("ME2N", "查询采购订单", "物料管理"),
    ]
    assert match_exact_tcode("请问 /nme23n 是什么？") == "ME23N"
    assert match_exact_tcode("权限管理有哪些 T-code 可用？") is None
    assert match_exact_tcode("ME23N / ME2N") is None


def test_transaction_code_never_matches_a_prefix_or_code_inside_another_identifier():
    assert match_exact_tcode("ME23N1 是什么？") == "ME23N1"
    assert match_exact_tcode("/APP/XYZ1 是什么？") == "/APP/XYZ1"
    assert match_exact_tcode("What does SU53 do in SAP GUI?") == "SU53"
    assert match_exact_tcode("1KE4 是干什么的？") == "1KE4"
    assert match_exact_tcode("F-02 是干什么的？") == "F-02"
    assert match_exact_tcode("F.01 是干什么的？") == "F.01"
    assert match_exact_tcode("stms 是什么？") == "STMS"
    assert match_exact_tcode("stms") == "STMS"
    assert match_exact_tcode("查 stms") == "STMS"
    assert match_exact_tcode("What is stms in SAP?") == "STMS"
    assert match_exact_tcode("How do I use stms?") == "STMS"
    assert match_exact_tcode("What does SU53 do in S4HANA?") == "SU53"
    assert match_exact_tcode("PFCG in FICO?") == "PFCG"
    assert match_exact_tcode("FICO里有哪些权限管理事务码？") is None
    assert match_exact_tcode("Which role does SU53 serve?") == "SU53"


def test_punctuated_and_numeric_prefix_codes_are_retained_in_source_rows():
    markdown = "| 事务码 | 用途 |\n| --- | --- |\n| F-02 | 条目一 |\n| F.01 | 条目二 |\n| 1KE4 | 条目三 |"
    assert [row.code for row in extract_tcode_rows(markdown)] == ["F-02", "F.01", "1KE4"]


def test_sap_context_does_not_change_reverse_lookup_terms():
    assert _purpose_terms("SAP 有哪些事务码可以用来查传输请求？") == _purpose_terms("有哪些事务码可以用来查传输请求？")
    terms = _purpose_terms("Which transaction codes can be used to bake a cake in SAP?")
    assert _purpose_overlap(terms, "maintain roles and authorization data") == 0

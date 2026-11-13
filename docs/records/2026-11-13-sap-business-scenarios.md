# SAPilot 场景规则和事务码查询验收

本次在独立工作树 `codex/sapilot-code-tcode` 开发并用本地测试 Bot 验收第 2、3 项。测试入口复用现有 FAQ、规范集合，以及单独导入的事务码资料。

| 场景 | 实际核验 |
| --- | --- |
| 代码分析 | ABAP、Java 均通过粘贴及源文件上传进入独立代码 Bot。核验了解读、规范检查、修改建议。文件限 UTF-8、48 KiB，索引状态为 `SKIPPED`。错误类型、无效编码、超限和跨会话读取均被拒绝。SDK 调用回归确认路由和分析阶段无法派发未授权工具。 |
| FAQ | 「SAP帐号锁定，不知道怎么提流程」定位到 `FAQBASI0002` 和对应来源。命中和未命中分别经用户确认后进入扩展。浏览器刷新后仍可确认，实际 Redis 验证覆盖旧轮次迟到、重复确认。 |
| 规范 | 《SAP开发自测规范》REPORT 输出测试返回「连续运行两次及以上」与适用条款。无适用依据时返回缺失提示。 |
| 技术咨询 | 追问「把上一条第 3 项展开」能引用上一条对应内容。联网关闭时未取得外部来源。启用网页读取后，成功读取 SAP Help 的 ABAP 用户管理页面并返回真实出处。新版动态页面样例未提取到正文，失败结果不作为引用。 |
| 事务码 | 用户提供的手册正查 `ME23N`，采购订单倒查 `ME2N`、`ME23N`、`ME2J`。权限补充资料正查 `SU53`，权限管理倒查 `SU53`、`PFCG`、`SU01`、`SUIM`。中英文同义问法、前缀误匹配和无关目的也纳入核验。浏览器显示四条权限出处。 |

事务码使用原有全文和向量索引，再回到已解析的表格确认事务码、用途、文档、章节和行位置。同义倒查需要时用同一嵌入模型对已召回的表格行比较用途。原手册和权限补充资料保留在本地，补充资料引用了 SAP Help 的 [授权检查](https://help.sap.com/docs/ABAP_PLATFORM_NEW/ad77b44570314f6d8c3a8a807273084c/526716b3439b11d1896f0000e8322d00.html)、[PFCG 概览](https://help.sap.com/docs/ABAP_PLATFORM_NEW/9737050ef01843f19572591b42128f1b/4c5bdc4997817511e10000000a42189b.html?version=202110.002)和 [ABAP 用户管理](https://help.sap.com/saphelp_scm700_ehp02/helpdata/en/47/fe89a62d204aa7e10000000a421937/content.htm)。

配置脚本从 `app/` 运行，默认预览。先准备已索引的事务码资料集合，并确认目标 Bot 的三个现有 Skill ID。应用时加入 `--apply`，需要外部工具的场景分别通过 `--technical-tool` 或 `--faq-tool` 指定项目允许的工具。

```powershell
python -m scripts.configure_sap_business_bots --user USER_ID --bot BOT_ID --tcode-collection COLLECTION_ID
```

契约回归分本地容器和 Windows 运行，共 230 项通过。事务码另用真实全文和向量索引执行 11 条断言。前端 TypeScript、Prettier、Ruff 及差异空白检查通过。两名审查代理分别复验了业务验收和项目规约中的阻断项。验收配置保留在本地测试入口。第 1 项的默认截图检索、钉钉客户端实机和云端部署未纳入本次运行验收。

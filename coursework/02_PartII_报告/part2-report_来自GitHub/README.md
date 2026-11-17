# Part II — LLM-Based Vehicle Control

课程报告与配套阅读材料。文件发布在仓库 study 的 part2-report/ 目录；仓库已设为私有，课程提交截止前请勿转为公开。

## 优先打开

- [技术报告 Word（可编辑）](PartII_Technical_Report.docx)
- [技术报告 PDF（阅读版）](PartII_Technical_Report.pdf)
- [技术报告 Markdown](PartII_Technical_Report.md)
- [中文阅读指南](中文阅读指南.md) · [Word版本](中文阅读指南.docx)
- [个人部分独立写作提纲](个人部分_独立写作提纲.md) · [Word版本](个人部分_独立写作提纲.docx)
- [图表、数据与论文来源索引](图表与资料索引.md)
- [给 Trae 的最终补充清单](给Trae_最终补充清单.md)
- [完整 ZIP 资料包](PartII_full_package_20261109.zip)

## 怎样下载

打开 Word 或 ZIP 文件后，使用文件页的 Download／下载原始文件按钮。PDF通常可直接预览。也可在仓库首页选择 Code → Download ZIP 下载整个仓库，报告在 part2-report/ 中。

## 写作状态

技术正文由AI辅助整理，个人反思与结论仍为空白，须由学生独立撰写。姓名、学号、课程信息及最终格式尚待补齐。本文不是已经完成个人部分的最终提交稿。

## 证据范围

- `evidence/fair_v3/`：96场人工规则与IDM对照实验。
- `evidence/qwen_real/`：8场真实Qwen单车案例、8场IDM基线与决策/执行日志。
- `evidence/derived_audit.json`：逐条日志重算，含失败等待总耗时约153.8秒。
- `source_snapshot/`：收到的原实验代码快照，并非后续叙述所称的最新修复代码。
- `figures/`：报告用图；架构图根据实际代码重绘。

原始证据副本保留原汇总口径；正文与派生审计注明已发现的差异。未新增付费API调用。原始数据和实验代码未为配合报告文字而修改。部分交付验证和高亮ego图仍待Trae补充，见补充清单。

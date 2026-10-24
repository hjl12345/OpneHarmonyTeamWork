# 来源与使用说明（NOTICE）

本工具包是《开源鸿蒙操作系统开发实践》课程的教学材料，由**北京理工大学 基础软件与系统实验室（BIT FSS Lab）**整理。
项目主页：https://gitcode.com/BIT-FSSLab

## 一、各部分来源与权利

| 目录 | 内容 | 来源与许可 |
|---|---|---|
| `slices/` | samgr、state_registry 源码切片 | 取自 OpenHarmony 官方仓库（`gitcode.com/openharmony/*`），**Apache License 2.0**，版权归 Huawei Device Co., Ltd. 及各贡献者。各仓 `LICENSE` 原样保留 |
| `manifest/` | OpenHarmony 7.0-Release 的 repo manifest | 同上，Apache License 2.0，文件头保留原始版权声明 |
| `scripts/` | oh_slice / oh_trace / oh_verify / oh_level | 课程自制教学工具，著作权归 BIT FSS Lab。供本课程学习与课程报告使用 |
| `README.md`、`examples/` | 使用说明与锚点范例 | 课程自制，同上 |

## 二、本包**不包含**

- 任何参考答案、示范答卷、评分数据
- 批改算法（`oh_grade.py`）与反作弊阈值
- 教师侧才有的切片与演示材料

## 三、转发与传播

- **可以**整包转给同班同学或学弟学妹，用于课程学习；请**整包转发**，不要删掉本文件与各仓 `LICENSE`。
- **不建议**把自己的分析报告、锚点清单、汇报 PPT 一并公开。这些内容一旦上网，后来者可直接照抄，
  课程的同届判重（文本相似度 + 锚点指纹）管不到跨年跨校，最终受损的是你自己这份作业的含金量。
- **不要**把切片里的 OpenHarmony 源码说成自己写的。引用时注明仓库与 tag，例如：
  `systemabilitymgr_samgr @ OpenHarmony-7.0-Release`。
- 若要**公开再分发** `scripts/` 里的工具或用于其他课程，请先联系实验室。

## 四、上传到 Git 仓库时的坑

切片目录里保留了 `.git`（浅克隆，用于核验快照版本）。把整个工具包放进自己的作业仓库再 `git add .` 时，
Git 会把 `slices/samgr`、`slices/state_registry` 当成 **submodule 引用**，推上去后别人 clone 下来是两个空目录。

正确做法（在作业仓库里，只对副本操作）：

```bash
# 方案一：保留代码，去掉嵌套版本库
find slices -name .git -type d -prune -exec rm -rf {} +

# 方案二：让 git 忽略它们，不进入提交
echo 'slices/*/.git/' >> .gitignore
```

不要把工具包**原样**当成交付物上传：教师侧批改只认 `report.md`、`anchors.md`、`meta.json` 与 `slides.pdf`，
一个 6MB 的切片副本对判定没有任何帮助。

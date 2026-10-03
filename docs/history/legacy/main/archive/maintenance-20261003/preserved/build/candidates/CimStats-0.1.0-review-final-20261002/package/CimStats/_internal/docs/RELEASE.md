# CimStats 0.1.0 发布流程

尚未发布。本文是门槛，不是当前源码或旧包已通过的声明。

## 统一源码与验收

精确合入已通过候选，关闭大图、网络布局、启动/关于未验项。VERSION、元数据、关于、文件资源与包名统一0.1.0；旧VERSION未更新不能打新标签。

冻结源后检查全部页面、真实单/多人、筛选、异常/取消/退出、过期结果拒收、导出和动效。矩阵：2880×1920/200%、1920×1080/100%、2560×1440/125%、3840×2160/175%、2560×1600/150%。另交1440×960主程序截图，用户通过后才打包。离屏/进程缩放不代替原生系统验收。

## 内容和许可

先读[分发审计](REDISTRIBUTION_AUDIT.md)及[第三方声明](../THIRD_PARTY_NOTICES.md)。审查当前源码、全部拟推refs、zip内容与最终包。

游戏Managed DLL、Unity、修改探针、个人数据、系统字体不因项目GPL获得再分发权。未核清权利者排除公开内容。

原spec曾收集Managed、probe、UnityEngine.dll、系统ICU和几乎整个docs。本轮主spec已将文档与项目资源改为明确清单，构建／发布脚本不再删除或替换旧目录；本地候选仍为维持现有解析收集游戏依赖和系统ICU，需逐项核清。目录完整性通过不表示可公开发行，详见[构建准备](preflight/BUILD-PREPARATION.md)。

已跟踪EXE/zip/DLL不会因.gitignore移出历史。保留本地档案，公开使用审计后快照或隔离副本清理历史，不直接改写施工仓库。

## 只读文件清单预检

作者的免费、非商业社区定位及非官方关系见[项目声明](PROJECT_NOTICE.md)；它不为 GPL 增加禁止商用条款，也不授权复制游戏 DLL。项目自有源码及符合原许可的材料可继续准备发布，与待核实的组合包分别处理。

在项目根运行 `py -3.12 tools/release_preflight.py`，默认只读取源码候选与现有分发清单，在标准输出逐项列出可包含、排除、待确认、理由及 SHA-256。现有包可用 `--mode package --target dist` 单独检查。需要保存可复核记录时使用 `--output docs/preflight/source.json`；只写该报告，不复制、打包、上传或删除文件。工具也检查当前发布文档的本地链接。

预检会报告游戏/probe/Unity、存档、本地个人路径、嵌套旧包、工作树及未提交状态；普通开源 DLL 与项目 Bridge 分别判断，不把 DLL 后缀本身视为禁止分发。它是准备与审查工具，不是许可、构建或公开发布授权；全部页面验收和用户截图批准门槛保持。

本轮结果与逐项报告见[只读预检复核](preflight/REVIEW.md)。报告是读取当时的快照；源码变化后应重新运行，不能用于批准未来构建。

## 构建与包体

用户截图批准、主控确认整合源冻结后，在项目内build/candidates的唯一新目录生成本地目录式候选，不覆盖dist。`build_portable.ps1`默认只显示准备状态；实际构建参数、精确快照与游戏依赖标记见[构建准备](preflight/BUILD-PREPARATION.md)，当前没有直接公开打包的命令。

记录提交/源码hash、锁定依赖、工具版本、运行库来源和输出SHA256。包内项目及第三方许可齐全；缺游戏依赖须有真实可用准备方式，不重新塞入无授权文件。

干净环境验证启动、图标、关于/协议、真实解析、导出、关闭、中文路径/权限。分别测EXE到解释器、启动图首帧和主窗就绪；Python启动页不能覆盖解释器前解包等待。

## GitHub

确认账号、仓库名、可见性、历史策略再推送，不推所有本地分支和旧tag。v0.1.0对应已验收提交。

Release附件建议：CimStats-0.1.0-windows-x64.zip、SHA256SUMS、发行说明、必要对应源码/构建材料与许可。EXE不回灌源码历史。GPL对应源码责任不能只用GitHub自动zip替代核查。

先草稿再复核，获得发布授权才公开；无渠道不编造链接。保留旧版本和本轮证据，不覆盖同版本包；本地文件处理遵循回收站要求。

官方参考：[Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)、[大文件与历史](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)。

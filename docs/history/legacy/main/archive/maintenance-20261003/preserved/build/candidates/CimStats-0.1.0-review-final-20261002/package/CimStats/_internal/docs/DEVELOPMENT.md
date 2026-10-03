# CimStats 开发说明

## 环境与入口

当前验证：Windows x64、Python 3.12、PySide6 6.11.2、PySide6-Fluent-Widgets 1.11.3。这不是全部Windows版本的支持承诺；依赖声明尚有版本范围，首发前需固定经验证的集合。

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe CIM2_SaveStats.py
```

优先根启动器。直接运行frontend/desktop_app.py会先导入桌面模块，不能用于证明启动图标最早显示时间。启动/关于候选未集成时，以当前提交实际行为为准。

## 游戏依赖

解析使用游戏托管程序集和本地探针，不是纯Python解析。现有CIM2_MANAGED_ROOT可指定自己合法安装的CIM2_Data/Managed，不构成再分发授权。

CIM2_RUNTIME_DATA_DIR、CIM2_PAYLOAD_DIR、CIM2_EXPORT_DIR控制对应数据/输出。探针生成使用CIM2_ASSEMBLY_SOURCE与CIM2_PROBE_OUTPUT，不能互相替代。源码仍有本机路径回退，纯净机器未必适用。

当前构建需要经哈希校验的CIM2 v1.6.3原版程序集和匹配探针。不要绕过校验或修改游戏安装目录。公开发行的本地依赖准备方案未完成前，不宣称克隆后能一键解析。

## 目录

|目录|用途|
|---|---|
|frontend|UI、共享控件与品牌资源|
|src|解析、统计、导出及当前测试|
|tools|开发工具|
|docs|用户和开发文档、本地研发证据；公开仅选最终材料|
|jobs、exports、analysis|本地任务与结果|
|.worktrees|项目内工作树，不上传|
|build、dist、archive|本地构建与历史，不直接全量推送|

保留技术模块和设置键，不为品牌改名改存档格式。强调字体用frontend/stats_typography.py，QSS、富文本、QPainter和量宽同源。

## 测试

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

pytest.ini收集src并将src/frontend加入模块路径。完整套件可能需要本地数据或桌面；缺少条件如实记录，不把跳过算通过。

纯组件可使用进程级QT_QPA_PLATFORM=offscreen；主窗口、系统DPI及全局输入串行、隔离设置。离屏和进程缩放不代替原生鼠标、任务栏、系统DPI。

性能报告注明样本、冷热缓存、内存及首帧/主窗就绪/解析完成分段；替身窗口不代表主程序或冻结包。

## 构建

见[发布流程](RELEASE.md)。构建脚本默认仅显示准备状态；本地目录式候选使用明确文档、许可与图标清单，不删除或替换旧包。当前解析所需游戏 DLL 只用于明确标记的本地审核候选，公开源码与本地候选分别选择；没有游戏依赖再分发授权时不上传完整运行包。

不全量暂存或覆盖他人改动，不随UI修改重写原始.save/probe。补丁按before/after范围审阅；旧测试证据不自动适用于新源码。

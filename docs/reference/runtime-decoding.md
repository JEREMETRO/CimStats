# 存档与运行时解码

适用 Cities in Motion 2 v1.6.3。数据输出来自实际存档，不以某份样例的城市、玩家、对象数量或负载偏移作为默认值。

## 容器与对象

[save_container.locate_payload](../../src/save_container.py)保留 UTF-16 元数据与缩略图包络，检查页对齐和零填充边界的 raw DEFLATE 候选，并验证 `FD 77 FD C9`负载标记。偏移随存档变化；不能硬编码单份样例的 `0x29000`。无法唯一定位负载时拒绝解析，不猜测边界。

对象负载包含大端数值、UTF-16BE 字符串、类型表、对象引用及共享对象。不得把负载当作普通 JSON 或依赖字符串搜索还原关联。通过 pythonnet 和隔离探针读取游戏序列化对象图；原始存档及原始程序集不原地修改，不运行 Unity 场景回调代替只读解析。

## 资源与输出

- `game_runtime/Managed/`提供程序集依赖，`data/Assembly-CSharp.probe.dll`及 `data/UnityEngine.dll`保留在仓库中。
- `CIM2_MANAGED_ROOT`、`CIM2_RUNTIME_DATA_DIR`指定运行时资源；`CIM2_PAYLOAD_DIR`、`CIM2_EXPORT_DIR`指定该任务的中间与导出目录。
- 命令行解析必须显式传入本地 `.save`，不要依赖调试脚本中的样例默认值。桌面程序为每次任务提供隔离输出位置。
- 生成的负载、CSV、工作簿与日志放在忽略的工作目录，实际存档和个人标识不提交。

## 关联与限制

- 线路制式取 `LineData.m_type`所引用 `VehicleTypeObject`的身份，不以燃料／能源字段猜测制式。
- 公司归属按稳定 ID 与对象引用映射；相同名称不证明同一公司，同公司多人不重复计数。多人城市模拟共享，见[多人同步](multiplayer.md)。
- 线路缓存可能没有重建；里程、预计时间与配车按路径及班次重算，并区分缓存值与推导值，见[线路指标](line-metrics.md)。
- 城市 `trip-number`不是线路发班；当前存档没有可无损还原的逐小时线路客流历史或首次启用日期，不以总客流均摊伪造。
- 实际存档中的对象数量、地图名、城市名、玩家标识是输入属性，不是业务常量。

实现入口：[extract_runtime_data.py](../../src/extract_runtime_data.py)、[history_contract.py](../../src/history_contract.py)、[parser_backend.py](../../parser_backend.py)。容器回写工具与只读统计是不同操作；任何回写应输出新文件并重新反序列化验证，不能在正常统计中覆盖输入。

# 城市页能源价格证据与待验用例

状态：2026-09-30 只读预检；城市页实现与独立运行验收均未开始。本文件不把秋山市 n6 截图当作本项目存档逐点复算。

## 已核对来源

- `D:\test\CIM2_MultiplayerAudit\baseline\CityManager.il.txt:4122` 至 `:4141`：`energy-prices` 的 `fuel`、`electricity` 两组分别从 `EconomyData.m_fuelPrice`、`m_electricityPrice` 转为 Int32 后直接调用 `HistoryData.SetData(..., 0)`。未见在写入时除以 100。
- `D:\test\CIM2_MultiplayerAudit\baseline\GraphPanel.il.txt:474` 至 `:479` 识别 `unit=money`；`:1319` 至 `:1332` 的对应分支调用 `Locale.FormatMoneyLong`。`D:\test\CIM2_MultiplayerAudit\baseline\Locale.il.txt:319` 至 `:353` 中该格式化函数对整数做 `/100` 与 `%100`，用于游戏货币形式的显示。图表选项 `m_options` 到具体 `unit=money` 的映射尚未证实，因此仅凭这些 IL 不能断言能源图每一个显示点都已走该分支。
- `D:\test\CIM2_SaveStats\exports\CIM2_城市历史指标_完整_quicksave.76561198362520556-76561198845688243_运行时.csv` 的一条历史样本显示 `electricity=68`、`fuel=147`，分母均为 0、非百分比、非增量。用户提供的秋山市 n6 游戏截图显示电力蓝线、柴油黄线，纵轴 0.00–2.00；该原存档尚未找到，不能与上述 quicksave 的样本值配对逐点验证。

## 独立验收用例

1. 在可追溯真实存档中抽取同一模拟时间的 `energy-prices/electricity` 与 `fuel` 原值，对照城市页卡片、图表轴值、悬浮提示及导出。若界面采用游戏的 money 显示格式，只做一次 `/100` 换算；原始记录继续保留原整数。分别覆盖零、正数和可获得的边界值，不对分母 0 做比例计算。
2. 图例采用用户指定的“电力”“柴油”，对应蓝、黄曲线身份在日／周／月切换、提示与导出中一致。截图只证明游戏图例与大致视觉，不证明本项目具体数值换算。
3. 查到能源图 `m_options` 资源映射或同一存档的游戏图点数据后，再将 `unit=money` 应用到能源图的证据链标为已证实。未补齐前不把原值称“价格指数”，也不赋予未经证实的物理货币单位。
4. 城市页切换与重新加载后，核对能源原值不被改写，卡片/图表/tooltip/导出不出现一处原值、一处二次 `/100` 或一处百分比的分歧。执行时保存原 `.save` 前后哈希，等待性能会话结束独占重载后再运行。

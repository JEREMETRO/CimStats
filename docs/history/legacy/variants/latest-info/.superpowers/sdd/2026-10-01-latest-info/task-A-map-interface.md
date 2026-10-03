# A 修订公开接口（给 B/D；2026-10-01）

模块 `src/map_name_source.py` 已可导入（纯 Python、无 Qt/CLR/解压/写入）。

- `display_session_city_name(data: dict) -> str`：B.set_session 即时城市显示与 A 快照完全同源；读取 data.save_path 最多16KiB文件头，优先真实头，可靠带来源原名 metadata 后备，不显示旧无来源文本/filename/tag。缺失返回“未提供城市名称”。
- `resolve_session_map_name(data: dict) -> MapNameInfo`：提供同一名称与来源/原始值；frozen dataclass 字段 `display_name, raw_reference, raw_map_name, internal_id, source, status, reason, format_version, read_bytes`。
- `read_save_map_name(path)` / `parse_save_map_header(bytes)` / `normalize_map_reference(raw, *, source='original-map-reference')` / `map_metadata_fields(path, *, runtime_name='', runtime_source='')` 为纯数据边界。

LatestInfoSnapshot 原有字段位置/含义保持；末尾增加默认值的 `city_source=''`, `city_raw_reference=''`, `city_raw_name=''`, `city_internal_id=''`, `city_name_reason=''`, `company_trend: Result | None=None`，旧构造器兼容。

今日趋势新 UI 使用 `snapshot.company_trend`：

- 综合键为 `(真实公司ID, '总计')`，由 `_quantity_trend` 先校验各公司完整已序列化制式类别；各公司缺小时/类别为 None，其他公司的缺测不抹去本公司有效点。
- 选具体制式键为 `(真实公司ID, 中文制式名)`，保留原始 Query 真实分类结果。
- query.companies 是真实当前所选 ID tuple；公司名称映射取 snapshot.companies，同名仍用 ID 区分。单公司一条、多公司每真实公司一条，不写死两条；无可查数据不伪造曲线。
- B 消费此字段画普通折线，原 `snapshot.trend` 继续保留现有聚合口径/缺口，13项公式未修改。

**窄接线边界已补齐（父追加授权）**：`frontend/report_model.py:metadata_display` 保持“地图名称”原键兼容，仅增加 `地图原始引用`、`地图原始名称`、`地图内部标识`、`地图名称来源`、`地图名称说明` 五个字段的直接透传；本次该文件 diff 只有一个五行映射 hunk，供父单列审核。新缓存 metadata 在 save_path 无法读取时可作为可靠后备；没有来源信息的旧缓存仍不升格为可靠名称。纯加载回归覆盖新来源后备及旧缓存拒绝推断，80项地图/模型定向通过。真实 MainWindow 输入有 save_path，头优先无需重解析旧缓存。

当前16384字节上限；只支持核验版本2013120900及GameState+SerializableMetaData类型序列。异常返回unknown，无文本扫描、文件名推断或payload处理。明确ASCII snake/kebab标识可读化并保留数字；地区/无版本标记数字剥离限已验证WorkshopID+完整名称对；通用仅剥显式v/version版本词。

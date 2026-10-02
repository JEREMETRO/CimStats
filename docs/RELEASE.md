# CimStats 发布流程

## 当前版本

**CimStats 0.1.0** 已发布，单文件 exe 可直接分发。

## 构建发布包

### 环境准备

1. Python 3.12
2. 游戏安装目录（用于获取运行时 DLL）
3. 项目依赖：`pip install -r requirements-dev.txt`

### 构建步骤

```powershell
# 设置环境变量
$env:CIMSTATS_LOCAL_REVIEW_BUILD = '1'
$env:CIM2_BUILD_MANAGED_ROOT = '<游戏 Managed 目录>'
$env:CIM2_BUILD_PROBE_PATH = '<探针路径>'

# 构建单文件 exe
py -3.12 -m PyInstaller --clean CIM2_SaveStats.spec

# 输出位于 build/onefile-dist/CimStats.exe
```

### 验证

1. 运行 `CimStats.exe` 确认 GUI 正常启动
2. 加载测试存档验证解析功能
3. 检查导出功能

## 发布检查清单

- [ ] 版本号已更新（`VERSION` 和 `src/app_metadata.py`）
- [ ] CHANGELOG.md 已更新
- [ ] 测试全部通过
- [ ] 单文件 exe 构建成功
- [ ] GUI 启动正常
- [ ] 存档解析正常
- [ ] 导出功能正常
- [ ] 文档已更新

## GitHub Release

1. 创建 tag：`git tag v0.1.0`
2. 推送 tag：`git push origin v0.1.0`
3. 在 GitHub 创建 Release，上传 `CimStats.exe`
4. 更新 Release 说明（从 CHANGELOG 复制）

## 文件清单

发布包包含：
- `CimStats.exe`（单文件，包含所有依赖）
- 源码（GitHub 自动打包）
- 许可文件（`LICENSE`、`THIRD_PARTY_NOTICES.md`）

## 版本管理

- 版本号格式：`major.minor.patch`
- 版本来源：`VERSION` 文件
- 元数据：`src/app_metadata.py`
- 历史版本保留，不覆盖

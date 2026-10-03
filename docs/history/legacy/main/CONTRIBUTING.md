# 贡献指南

感谢你对 CimStats 的关注！

## 报告问题

提交 issue 时请包含：
- CimStats 版本和 Windows 版本
- 游戏版本和存档类型（单人/多人）
- 问题描述、复现步骤和预期行为
- 如有，附上截图（请移除个人路径、身份和存档名）

**请勿上传**：`.save` 文件、游戏 DLL、密钥、完整 `jobs/` 目录或未脱敏日志。

## 提交代码

1. Fork 仓库并创建功能分支
2. 遵循现有代码风格和 Fluent 控件规范
3. 添加或更新测试（如有）
4. 确保所有测试通过：`python -m pytest -q`
5. 提交 Pull Request，描述改动目的和范围

## 开发环境

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

详见[开发说明](docs/DEVELOPMENT.md)。

## 代码规范

- UI 使用共享 Fluent 控件、配色和字体
- 数据修改需提供可复算的测试用例
- 保留无关业务逻辑和设置
- 新依赖需记录版本、许可和用途

## 许可

贡献即表示你同意按项目 [LICENSE](LICENSE)（GPL-3.0-only）提供代码。第三方材料保留原许可。

# 开发与发布流程

根目录 Git 仓库统一管理源码、研究档案和版本构建；不嵌套仓库，不改写历史。
没有远程仓库时只做本地发布，不声称已推送。

| 目录 | 唯一职责 |
|---|---|
| dist | 当前正式版，恰好 EXE、README.md、VERSION.json 三个文件 |
| archive/versions/v版本 | 不可覆盖的正式发布，源码包、校验、验证凭据 |
| archive/builds | 标注为非正式的历史中间包，仅追溯 |
| build/staging/v版本 | 尚未发布的候选，不能作为日常入口 |
| build/runtime、build/pyinstaller | 构建中间产物 |
| jobs | 运行任务、迁移数据、回归输出，不提交 Git |
| archive/history | 不参与运行的历史研究源码和记录 |

1. 从已验证版本创建 fix 或 feature 分支；先复现、增加回归测试，再修改。
2. 更新 VERSION、CHANGELOG 和当前说明；运行 `py -3.12 -m pytest -q`。
3. 独立审查后提交源码。两个未提交的本地探针不参与发布。
4. 执行 `./build_portable.ps1`。脚本要求已提交的源码和未占用的候选目录；
   自动测试后构建、检查内置依赖，生成包含源码提交与 SHA256 的 VERSION.json。
   失败候选保留在 build 中供诊断，绝不写入 dist。
5. 使用真实存档验证确切包体，例如：

   `py -3.12 src/verify_candidate.py build/staging/v0.5.1 analysis/秋山市/秋山市n3.save analysis/秋山市/秋山市n4.save`

   这会校验输入存档未变化、UTF-8 输出、两份 XLSX 无错误单元格，并生成绑定 EXE 哈希的 validation.json。
   另做桌面启动、运行路径和界面检查；记录到版本 VALIDATION.md。
6. 关闭正在使用的 dist 程序，再执行 `./publish_release.ps1`。脚本校验候选、验证凭据、源码 HEAD 和测试。
   旧 dist 必须为空或是与已有归档完全相同的正式版；未知文件会阻止发布。
   在 build/publish 临时目录准备源码包及校验记录，归档后更换 dist；更换失败恢复旧目录。
7. 补充发布说明及索引，提交版本归档；在 main 验证测试及最终目录，再创建附注版本标签。

不能重复发布同一个版本。不得把候选改名冒充新版、复用不同 EXE 的验证凭据、将 jobs 放进发布包。
若发布中断，保留已归档版本，核查后恢复入口，不删除或覆盖已发布版本来重试。

旧程序不重新打包，因此旧版若被再次运行仍会在其 EXE 旁生成 jobs；日常入口始终是 dist 当前版。
2026-09-25 迁移凭据位于 jobs/migrated/2026-09-25/migration.json，迁移后结果保留来源目录层级。

环境安装：`py -3.12 -m pip install -r requirements-dev.txt`。构建使用本机 CIM2 v1.6.3 托管程序集副本，
不修改游戏安装目录或输入存档。pytest.ini 只收集当前 src 测试，历史研究探针不作为测试运行。

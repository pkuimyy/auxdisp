# AuxDisp Codex 用量应用

[English version](../en/README.md)


本目录目前只是工程占位项目，尚无 Codex 账号处理、用量轮询、屏幕渲染或其它应用业务逻辑。

驱动尚未通过首次实机验收，也没有 PyPI 发行版本，因此本项目目前没有驱动运行时依赖。等通过验收的驱动版本可从 PyPI 安装后，在 `pyproject.toml` 中声明普通的有界依赖，例如 `auxdisp-driver>=0.1.0,<0.2.0`，然后用 `uv lock --no-sources` 更新本项目独立的锁文件。不要添加本地路径、editable、workspace 或 Git 依赖。

达到该发布门槛前，不应开始开发或发布此应用。

# auxdisp-codex-quota preview / 预览来源

`auxdisp-codex-quota-demo.png` 是当前渲染器生成的 **Demo 离线预览**，1280×720 PNG；不是实机照片或真实账户运行证据。数据来自包内 `data/demo.json` 的首个合成账户，名称改为 `DEMO ACCOUNT`，日期时钟固定为北京时间 2026-11-10 20:00。图片不包含真实账户名称、邮箱、ID 或认证信息。

The image is a **Demo offline preview** from the current renderer, not a physical-device photograph or evidence of real-account operation. It uses the first bundled synthetic account, renamed `DEMO ACCOUNT`, and a fixed clock at 2026-11-10 20:00 UTC+08:00. No real identities or credentials are included. A publishable device photograph remains a future addition.

在应用目录、按开发指南配置共享缓存并同步环境后重现 / From the application directory, after configuring the shared cache and syncing its development environment:

```powershell
uv run --locked --no-sources python -c "from dataclasses import replace; from datetime import datetime; from pathlib import Path; from auxdisp_codex_quota.preview import FixtureCollector; from auxdisp_codex_quota.config import Settings; from auxdisp_codex_quota.model import AccountStore; from auxdisp_codex_quota.render import Renderer, make_page; a=replace(FixtureCollector().collect()[0], alias='DEMO ACCOUNT', email=''); now=datetime.fromisoformat('2026-11-10T20:00:00+08:00'); s=AccountStore(); s.success((a,),now); image=Renderer(Settings()).render(make_page(s.snapshot,a.key,now,Settings(),card_page_index=0)); image.save(Path('../../docs/assets/auxdisp-codex-quota-demo.png'),optimize=True)"
```

重置时间按本机时区绘制；重现此图片时使用 UTC+08:00。Windows 默认等宽字体及同字号中文回退可能与其他系统不同。图片随项目采用 GPL-3.0-or-later。

Reset times use the local timezone; reproduce this image with UTC+08:00. Font appearance can vary by platform. The image is distributed under the project's GPL-3.0-or-later license.

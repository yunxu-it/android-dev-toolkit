# 文档索引 / Documentation

日常使用只需阅读 [中文 README](../README.zh-CN.md) 或 [English README](../README.md)。
Windows 首次在根目录运行 `./install.ps1`，之后输入 `adt` 打开全屏终端界面。
使用侧栏或 `1/2/3` 导航，设备列表用 ↑/↓ 和 Enter，`r` 刷新，Esc 返回/取消，`q` 退出。

## 使用与设计

- [配置与设备选择规则](configuration.md)
- [架构与模块边界](architecture.md)
- [阶段计划与完成状态](roadmap.md)
- [M1 范围与终端交互决策](decisions/0001-m1-scope.md)

## 贡献与维护

- [依赖与许可证审查](dependencies.md)
- [开发规范](../AGENTS.md)
- [版本记录](../CHANGELOG.md)

## 目录说明

```text
android-dev-toolkit/
├── install.ps1              Windows 首次安装入口
├── README.md / README.zh-CN.md
├── AGENTS.md / CHANGELOG.md / LICENSE
├── pyproject.toml / uv.lock Python 项目与依赖锁
├── src/adt/                 应用源码
├── tests/                   自动化测试
├── docs/                    公开设计、配置与路线图
├── .github/                 GitHub Actions 配置，参与版本控制
├── .git/                    本地 Git 数据，不手动移动
├── .venv/                   uv 标准项目环境，不参与版本控制
└── .adt-local/              本地生成内容，不参与版本控制
    ├── cache/               pytest / Ruff / mypy 缓存
    ├── uv-cache/            uv 安装缓存
    └── …                    本地开发材料与隔离安装产物
```

点开头通常表示配置目录或工具内部数据，并不都是临时文件。三类检查缓存已集中存放，
以后不会重新在根目录生成 `.pytest_cache`、`.ruff_cache`、`.mypy_cache`。
`.git`、`.github` 和 `.venv` 保留标准位置，避免引入额外环境参数。

## 版本控制边界

提交源码、测试、`pyproject.toml`、`uv.lock`、`.github`、`.gitattributes`、`.gitignore`、
安装入口、开发规范与文档。`uv.lock` 是依赖复现依据，需要提交。
内部任务书、本机验收记录和环境故障排查过程不属于公开文档，留在本地忽略目录。

忽略 `.adt-local`、`.venv`、字节码、兼容旧位置的三类缓存、构建/测试报告、IDE 和
系统本地文件；同时忽略 `.env`、签名密钥、ADB 授权密钥、本地 Android 配置、APK/AAB
及日志。只允许提交虚构且无密钥的 `.env.example` 等示例。
不采用忽略所有点文件或所有 TOML/JSON 的规则，避免隐藏必要配置和测试数据。
真实设备信息只用于本地输出；若手动保存，请放 `.adt-local`，分享前自行审查。

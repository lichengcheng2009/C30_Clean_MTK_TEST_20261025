# 全网最完整最适合小白的 **C30教育平板解控刷机**教程
<p align="left">
  <img src="./sanlin_high_school_vector.svg" alt="三林中学校徽" width="180">
</p>





# 懒人步骤：

如果你不了解如何刷机，只是想要解锁c30这台设备，那么请把c30通过usb线（质量好的能传输数据的非纯充电线）把你的c30连接上电脑（win推荐，Linux也可，mac欠测试但是未证明不可），并且直接让你的coding agent看本仓库，给予他 **完整访问权限** ，让你的coding agent按照本仓库的skill来做就好。期间泡杯茶看看屏幕，过一会儿就好了。


# 能做到什么？

| 项目 | 原厂 C30 | 项目目标 |
| --- | --- | --- |
| 操作系统 | Android 11 | 仍然是 Android 11 |
| 桌面 |厂商定制界面 | 自制「C30 桌面」|
| 应用界面 | 由原厂配置决定 | 提供应用列表、搜索 |
| 系统设置 | 可能受到管理策略限制 | 新桌面提供设置入口 |
| 管理组件 | 集成「皆成守护孩子端」 | 用不含监管的桌面组件替代 |
| Wi-Fi、相机、触摸 | 使用原厂驱动 | 保留原驱动 |
| 第三方 App | 取决于原厂策略 | 能够正常启动兼容的应用 |

# C30 固件工具与原厂恢复指南

本项目面向板号 `tb8788p1_64_bsp`、产品标识包含 `TDC30-Ai10H` 的 Android 11 C30。仓库提供备份校验工具、原厂恢复用的分区表、项目源码和刷写脚本。下载源码后，可以立即做离线检查。恢复原厂系统时，需要准备自己设备的匹配备份和厂商或管理员授权的刷机工具。

## `super.img`

C30 的 `super` 分区存放 Android 系统镜像。用设备原本支持的读回方式备份时，可将它保存成 `super.img`。这份文件来自你的设备，需在本地保留。同名 C30 的硬件和系统版本可能不同，先核对板号、产品标识和备份哈希。

| 你的目标 | 在本地准备的文件 | 通过条件 |
| --- | --- | --- |
| 检查下载的源码 | 仓库源码 | `python tools/verify_files.py --source` 显示 `PASS SOURCE ONLY` |
| 准备恢复原厂系统 | 从自己设备读回的原厂镜像，核对后放在 `rollback/super.img` | `python tools/verify_files.py --stock` 显示 `PASS STOCK FILES` |
| 校验手头已有的完整项目测试包 | 原厂 `rollback/super.img`，以及另行准备的项目 `images/super.img` | `python tools/verify_files.py` 显示 `PASS PACKAGE` |

## 从自己的备份准备原厂恢复

1. **准备电脑和工作目录。** 从 GitHub 页面选择 **Code → Download ZIP**，解压到例如 `C:\C30`。装好 64 位 Python 3.11 或以上，并让 `python` 在终端可用。打开含 `README.md` 和 `tools` 的文件夹，在这里启动 PowerShell。Linux 也可以做离线校验，真机操作的平台由授权刷机工具决定。
2. **确认设备和备份。** 在设备记录或厂商资料中核对板号、产品标识。另行导出照片、文档和应用里的资料。如果还没有固件备份，用这台设备已有的厂商或管理员授权的读回方式取得原厂备份。先保留原件，再将 GeekFlashTool 备份解压到 `work` 下的一个目录。下面以 `work/c30-stock` 为例，该目录内应直接包含 `super.img`、`vbmeta.img`、`preloader_tb8788p1_64_bsp.bin` 和 `MT6771_Android_scatter.txt`。
3. **离线核对备份。** 运行下面前两条命令。第二条出现 `PASS STOCK BACKUP` 后，将备份里的 `super.img` 复制到 `rollback/super.img`，再执行最后一条。看到 `STOP`、找不到文件或哈希不符时，在该步停止。请使用与你的固件版本对应的厂商恢复包，或请维护者核对兼容性。

   ```powershell
   python tools/verify_files.py --source
   python tools/check_original_backup.py "work/c30-stock"
   # 确认出现 PASS STOCK BACKUP 后再复制
   Copy-Item work/c30-stock/super.img rollback/super.img
   python tools/verify_files.py --stock
   ```

4. **按授权流程恢复。** 使用支持该设备的厂商恢复工具或管理员授权工具确认连接，并核对设备当前分区布局。若工具支持 scatter，可使用仓库中 `rollback/MT6771_Android_scatter.txt`，在界面核实只选中 `super` 和 `vbmeta` 并对应 `rollback/` 下的两份镜像。选择逐分区写入。连接认证或分区核对失败时停止，交由厂商或管理员处理。
5. **回读并检查开机。** 用授权工具回读 `super` 和 `vbmeta`，保存为本仓库 `readback/super.img` 和 `readback/vbmeta.img`。运行 `python tools/verify_files.py --readback original`，确认两个文件都显示 `PASS readback`，再按厂商流程重启。开机后检查触摸、Wi-Fi、旋转和相机。恢复出厂设置会清除个人资料，请按厂商流程单独处理。

## 常见卡点

| 提示 | 先检查什么 |
| --- | --- |
| `python` 找不到 | 检查 Python 安装与 PATH，关闭终端重新打开后运行 `python --version`。 |
| `Missing backup file` | 把含四个文件的那一层目录传给脚本。RAR 和外层目录需要先解压或进入下一层。 |
| `Hash mismatch` 或布局不符 | 核对板号、固件版本和备份来源。当前清单对应项目记录中的原厂版本，保留清单和原始备份。 |
| 完整包检查提示缺少 `images/super.img` | 手头只有原厂备份时，使用上面的 `--stock` 流程。 |
| 写入报错或回读不一致 | 保留错误信息，按厂商恢复流程核实设备状态后再进行下一步。 |

## 给 Agent 和贡献者

在仓库根目录打开 Codex，选择 `$c30-flash`。其他 Agent 可以读取 `AGENTS.md` 并进入 Skill。Skill 会根据实际结果区分文件校验、设备确认、写后回读和启动。见 [Skill](.agents/skills/c30-flash/SKILL.md)。

源码构建、清单维护和测试见 [构建与发行说明](docs/BUILD_AND_RELEASE.md)。

## 开源许可证

本仓库原创代码采用 **GNU GPL v3.0（GPL-3.0-only）**，完整条款见 [LICENSE](LICENSE)。

授权范围为仓库根目录的原创 `.cmd` 脚本、`sources/` 中的原创 Python 和 Java 源码及 `AndroidManifest.xml`，以及 `tools/` 根目录的原创 Python 辅助脚本、`tests/` 中的原创测试代码和 `.github/workflows/` 工作流配置：

- `tools/check_layout.py`
- `tools/prepare_read.py`
- `tools/run_mtk.py`
- `tools/verify_files.py`

你可以按 GPL-3.0 使用、修改和分发这些代码，包括商业使用。分发修改版或基于这些代码的衍生程序时，应遵守 GPL 对许可证、声明和相应源码提供等方面的要求。软件按许可证条款提供，不作担保。

## 第三方内容及授权范围

上述授权仅适用于仓库贡献者有权授权的原创代码，不覆盖整个文件夹中的所有文件。

- `tools/mtkclient/` 保留其自身的 [GPL-3.0 许可证](tools/mtkclient/LICENSE)及原有版权声明。
- `tools/python-packages/` 中的依赖保留各自的许可证及版权声明。
- 第三方安装包、驱动、加载器、预加载器、固件及镜像（包括 `images/`、`rollback/`、`tools/device_preloader.bin` 和 `tools/UsbDk_1.0.22_x64.msi`）不因本仓库公开或添加 GPL 而获得新的开源授权；使用、修改和再分发仍须遵守各自适用的授权。
- 其他二进制文件、签名密钥、验证记录和文档不在上述源码许可范围内。本声明不授予第三方商标或其他权利。

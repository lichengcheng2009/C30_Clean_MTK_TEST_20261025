---
name: c30-flash
description: Validate a user-supplied C30 GeekFlashTool backup, check stock or full-package readiness, and guide authorized stock recovery and readback for tb8788p1_64_bsp / TDC30-Ai10H devices.
---

# C30 固件校验与恢复

在仓库根目录工作，使用 64 位 Python 3.11+。先确认用户想恢复原厂、检查已有测试包，还是只验证源码。面向 `tb8788p1_64_bsp`、产品标识包含 `TDC30-Ai10H` 的设备。每台设备可用授权工具读回自己的 `super` 分区，保存成原厂 `super.img`。核对用户的设备标识、固件版本和备份来源。

| 目标 | 命令 | 通过后说明 |
| --- | --- | --- |
| 检查检出内容 | `python tools/verify_files.py --source` | 跳过两份本地 super。报告源码通过。 |
| 核对设备原厂备份 | `python tools/check_original_backup.py "work/c30-stock"` | 用实际解压目录。三份文件和八个布局项匹配后，准备 `rollback/super.img`。 |
| 核对原厂恢复文件 | `python tools/verify_files.py --stock` | 跳过项目版 `images/super.img`。报告原厂文件在离线检查中通过。 |
| 核对已有项目测试包 | `python tools/verify_files.py` | 两份本地 super 均要通过 SHA-256。报告完整包离线结果。 |

先做离线核验。文件缺失或哈希不符时，报出失败的文件和当前路径。保留清单预期值，查找与设备固件版本匹配的厂商包。把固件、读回文件、凭据和设备身份数据留在本地。

只有用户提出真机恢复时才打开[备份与恢复](references/backup-and-recovery.md)的操作步骤。用设备已有的授权工具，先核对实时设备与分区布局。写入和清除分别以用户明确授权为准。认证、写入或回读失败时，在当前步骤停下并报告。用户只要求检查时，完成所需的离线检查即可。

汇报实际通过的阶段。用通过回读表示两个分区各自哈希匹配，并单独报告设备启动和硬件检查情况。

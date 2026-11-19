# 备份与恢复

## 从设备备份开始

请用户提供已解压的 GeekFlashTool 原厂读回目录，或由用户通过设备已有的授权工具读回。可以把目录放在 Git 忽略的 `work/` 下。`tools/check_original_backup.py` 只读取文件，参数是直接包含以下四个文件的目录。

| 备份内容 | 校验通过后的用途 |
| --- | --- |
| `super.img` | 原厂系统分区镜像。复制到 `rollback/super.img`。 |
| `vbmeta.img` | 与仓库内 `rollback/vbmeta.img` 比对。 |
| `preloader_tb8788p1_64_bsp.bin` | 与仓库内 `tools/device_preloader.bin` 比对来源。 |
| `MT6771_Android_scatter.txt` | 比对八个分区的起始地址、大小和存储区域。 |

每次使用原始备份的副本。适用的镜像和布局由仓库清单限定，其他固件版本应使用其对应的厂商恢复包。项目核对过的 GeekFlashTool 归档缺少 `userdata.img`。使用前确认用户已另行备份需要保留的个人数据。

## 经授权的原厂恢复

1. 从仓库根目录运行 `python tools/verify_files.py --stock`，确认 `PASS STOCK FILES`。核对目标设备和它的实时分区布局。请用户指定该设备已有的授权刷机工具。连接或认证失败时交由设备管理员或厂商处理。
2. 确认用户授权写入后，在工具里使用逐分区写入。支持 scatter 的工具可使用 `rollback/MT6771_Android_scatter.txt`，并核对实际选中且写入的只有 `rollback/` 下的 `super.img` 和 `vbmeta.img`。
3. 写入成功后用授权工具回读。把两个分区分别保存为 `readback/super.img` 与 `readback/vbmeta.img`，运行 `python tools/verify_files.py --readback original`。两项均须显示 `PASS readback`。如果写入或回读失败，保留日志并按厂商流程核对设备状态。
4. 按厂商流程启动，验证触摸、Wi-Fi、旋转和相机。恢复出厂设置会清除个人资料，在用户明确要求时单独处理。

针对人的逐步说明及常见错误见[仓库 README](../../../../README.md)。完整项目包的源码、构建和维护范围见[构建与发行说明](../../../../docs/BUILD_AND_RELEASE.md)。

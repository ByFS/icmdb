# 零命令采集方案(内核接口为主)

## 背景与目标

部分被管机器无法安装 dmidecode / ipmitool 等采集命令(精简系统, 无包管理器, 安全限制)。目标是让采集器**不依赖任何外部命令**, 只读 Linux 内核自带的接口(`/proc`, `/sys`, SMBIOS 表)也能采到尽量多的字段; 命令存在时作为**增强源**补齐内核接口没有的字段, 全部失败则按现有语义置 null。

原则: **内核接口为主, 命令为增强, 自动降级**。

## 字段矩阵

| 类别 | 字段 | 现状命令 | 无命令来源 | root | 说明 |
|---|---|---|---|---|---|
| os | hostname | hostname -f | /proc/sys/kernel/hostname | 否 | |
| os | version | 读文件 | /etc/os-release PRETTY_NAME | 否 | 现状已是纯文件读 |
| os | kernel | gopsutil(读文件) | /proc/version | 否 | 现状已无命令 |
| os | virt | systemd-detect-virt | /sys/class/dmi/id/sys_vendor 兜底(已实现) | 否 | 命令失败时已有 DMI 兜底 |
| mgmt | mac/ip | gopsutil | /proc/net 解析 | 否 | 现状已无命令 |
| nics | 全部 | gopsutil | /proc/net 解析 | 否 | 现状已无命令 |
| cpu | slot/model | dmidecode -t processor | /proc/cpuinfo 的 model name(单路机); 多路 slot 需要 SMBIOS 表 Type 4 | 否 | |
| memory | 槽位明细(厂商/型号/PN/SN/速度) | dmidecode -t memory | 直接解析 SMBIOS 表 /sys/firmware/dmi/tables/DMI 的 Type 17 | 是 | 表文件 0400, 自写 Go 解析器约 200 行 |
| memory | 总量兜底 | - | /proc/meminfo | 否 | 无表权限时的降级字段 |
| disks | 型号/SN/类型/容量 | lsblk | /sys/block/*/device/{model,serial,type} + size | 否 | 本机已验证可读 |
| chassis_serial_number | 机箱 SN | dmidecode | /sys/class/dmi/id/chassis_serial | 是 | 序列号类文件内核层即 root-only |
| psus | 全部 | ipmitool | 无标准内核接口 | - | 无命令时置 null(现状语义) |
| gpu | uuid/name/size/驱动版本/PCI 号 | nvidia-smi | /sys/class/drm/*/device/{vendor,device} PCI ID + pci.ids 名称映射 | 否 | SN/驱动版本/显存无命令时置 null |

## 降级策略

每个字段的取值顺序:

1. 命令源存在且成功(信息最全, 例如 dmidecode 的 SPD 全字段, nvidia-smi 的 SN/驱动)
2. 内核接口(上面的无命令来源)
3. 全部失败 → null(现有语义: 视为未采集, 不清库中旧值)

实现上每条采集路径封装为「命令源 + 内核源」两个函数, 先试命令再试内核; `--debug` 打印各自失败原因, 方便排查降级发生在哪一层。

## 实现阶段

- **阶段 1: sysfs/proc 基线**(无 root 也工作): hostname, OS 三字段, virt, mgmt, nics, CPU 型号, 磁盘四字段, 内存总量兜底。改动小, 覆盖大多数字段。
- **阶段 2: SMBIOS 解析器**(替代 dmidecode, 需 root): 自写纯 Go 解析 /sys/firmware/dmi/tables/DMI, 输出 Type 17 内存槽位明细与 Type 4 CPU 槽位。约 200 行, 无第三方依赖(对比 go-smbios 库: 少一个依赖, 但解析器需自测)。
- **阶段 3: 命令增强层**(可选优化): 有 dmidecode/ipmitool/nvidia-smi 时优先用, 补 PSU、GPU 详情; 逻辑在阶段 1/2 完成后加, 就是包装「命令源优先」的取值顺序。

## root 依赖说明

- 序列号类字段(机箱/内存 SPD/GPU SN)在内核层面即 root-only, 换任何方案都无法绕过, 不是命令依赖问题。
- 非 root 可获得: hostname, OS, virt, mgmt, nics, CPU 型号, 磁盘型号/SN(视内核版本, 本机实测可读), 内存总量。
- SMBIOS 表(/sys/firmware/dmi/tables/DMI)为 root 可读。

## 验证方式

- 单机对比: `--print --debug` 在有命令与删掉命令的同一台机器上各跑一次, 对比 JSON 与 DEBUG 降级日志。
- 覆盖机型: 裸金属(Dell/HPE/浪潮), VMware/KVM 虚机, 容器(无 /sys 权限时看 null 语义)。
- 验收: 无 dmidecode/ipmitool 的机器上, 除 PSU 与 GPU 详情外其余字段与有命令时一致; 有命令时行为与现状一致(回归)。

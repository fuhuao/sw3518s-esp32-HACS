# SW3518S PD快充充电器（Home Assistant 集成）

一个基于 **ESP32-S3 + SW3518S 全协议快充模块** 的 Home Assistant 自定义集成，通过 MQTT 实时监控快充充电器的输出电压、电流、功率、芯片温度与当前协商的快充协议，支持远程开关快充输出，并可单独启用/禁用各快充协议。**数据全程本地流转，不上传任何云端。**

![iot_class](https://img.shields.io/badge/iot_class-local_push-blue)
![HA](https://img.shields.io/badge/Home%20Assistant-2024.4%2B-green)
![hacs](https://img.shields.io/badge/HACS-1.30.0-orange)
![version](https://img.shields.io/badge/version-v1.0.4-blue)

---

## ✨ 功能特性

- **实时监控**：输出电压、输出电流、输出功率、芯片温度（1s 刷新，MQTT 推送）
- **快充协议识别**：自动显示当前协商的协议 —— PD2.0 / PD3.0-PPS / QC2·3·4+ / SCP（华为超级快充）/ VOOC（OPPO 闪充）/ FCP 等
- **协议开关**：可单独启用/禁用 PD / QC / SCP / VOOC / FCP 快充协议（需 ESP32 固件配合）
- **远程控制**：一键开关快充输出（HA 下发 MQTT 指令 → ESP32-S3 → SW3518S）
- **统一设备卡片**：所有实体自动归属到同一个「SW3518S PD快充充电器」设备下
- **图形化配置**：添加集成时只需填写 MQTT 主题前缀，无需手写 YAML
- **HACS 支持**：可通过自定义仓库一键安装与升级

> ⚠️ 能力边界：PD 的 9V/12V/20V 电压档位由 **SW3518S 硬件与手机 CC 引脚协商**决定，本集成只能读取协商结果、开关输出，**不能由 HA 强制指定电压档位**。

---

## 🔧 工作原理

```
┌─────────┐   USB-C/A   ┌──────────────┐   I2C    ┌───────────┐   WiFi/MQTT   ┌──────────────────┐
│  手机    │ ◄─────────► │ SW3518S 快充板 │ ◄──────► │ ESP32-S3   │ ◄────────────► │ Home Assistant   │
└─────────┘   PD/QC/SCP  └──────────────┘  SDA/SCL └───────────┘  state/cmd     └──────────────────┘
             硬件完成握手                            解析寄存器并上报 JSON           订阅/发布 MQTT
```

- **SW3518S**：硬件完成全部快充协议握手（PD 的 CC 引脚 BMC 报文），内置降压功率级，MCU 无需处理任何 PD 底层协议；
- **ESP32-S3**：通过 I2C 读取 SW3518S 的电压/电流/温度/协议状态，经 WiFi-MQTT 发布 JSON 到 HA，同时订阅命令主题控制输出开关与各协议位；
- **本集成（HA 侧）**：订阅 `state` 主题解析 JSON 生成实体，向 `cmd` 主题发布指令实现远程控制。

---

## 📦 硬件要求

| 组件 | 说明 |
|---|---|
| ESP32-S3 开发板 | 任意带 WiFi 的 ESP32-S3 |
| SW3518S 快充模块 | 成品功率板（推荐）或按 datasheet 自制 |
| 直流电源 | 12–24V（供电给 SW3518S 功率级） |
| 手机/设备 | 用于触发快充测试 |

### 接线表（ESP32-S3 ↔ SW3518S）

| ESP32-S3 | SW3518S | 说明 |
|---|---|---|
| GPIO21 (SDA) | SDA | I2C 数据 |
| GPIO22 (SCL) | SCL | I2C 时钟 |
| GND | GND | **必须共地** |
| 3V3 | — | ESP32-S3 独立供电，勿从 SW3518S 取电 |

> 🚨 **安全警告**：SW3518S 的 CC1/CC2、DPC/DMC 直接连接 Type-C 母座，**严禁接到 ESP32-S3 任何 GPIO**（VBUS 最高可达 20V，远超 ESP32-S3 的 3.6V 耐压）。I2C 若无板载上拉，请在 SDA/SCL 各加 4.7K 上拉到 3.3V。

---

## 🤖 ESP32 固件要求

> 📘 **固件开发请直接照做 [FIRMWARE_PROTOCOL.md](FIRMWARE_PROTOCOL.md)** —— 里面是完整的 MQTT 协议约定：主题、状态字段、控制指令、协议 key 对照表、处理流程伪代码，照抄字符和命令即可。

固件负责：读取 SW3518S 寄存器 → 组装 JSON → 发布到 `{prefix}/state`；订阅 `{prefix}/cmd` 执行开关与协议控制指令。

### MQTT 主题约定

| 主题 | 方向 | 说明 |
|---|---|---|
| `home/sw3518s_charger/state` | ESP32 → HA | 状态上报 JSON |
| `home/sw3518s_charger/cmd` | HA → ESP32 | 控制指令 JSON |

### 状态 JSON 字段（字段名必须严格一致）

```json
{
  "vout_mv": 12120,
  "iout_c_ma": 2450,
  "power_w": 29.69,
  "temp_c": 47.5,
  "proto_name": "PD3.0-PPS",
  "output_en": true,
  "proto_en": {"pd": true, "qc": true, "scp": true, "vooc": true, "fcp": true}
}
```

| 字段 | 类型 | 单位 | 说明 |
|---|---|---|---|
| `vout_mv` | int | mV | 输出电压 |
| `iout_c_ma` | int | mA | C 口输出电流 |
| `power_w` | float | W | 输出功率 |
| `temp_c` | float | ℃ | 芯片温度 |
| `proto_name` | string | — | 快充协议名称（如 PD3.0-PPS / SCP / VOOC） |
| `output_en` | bool | — | 输出开关状态 |
| `proto_en` | object | — | 各协议启用状态：`pd`/`qc`/`scp`/`vooc`/`fcp` 对应布尔值 |

### 控制指令 JSON

```json
{"cmd":"output_on"}
{"cmd":"output_off"}
{"cmd":"set_proto","proto":"pd","enable":true}
{"cmd":"set_proto","proto":"qc","enable":false}
```

> `set_proto` 的 `proto` 取值：`pd` / `qc` / `scp` / `vooc` / `fcp`。

> 推荐使用 ESP-IDF / Arduino 编写固件，驱动库可参考 `h1_SW35xx`（开源 SW3518S I2C 驱动）。

---

## 📥 安装

### 方式一：HACS（推荐）

1. HACS → 右上角「⋮」→ **自定义仓库**；
2. 填入仓库地址 **`https://github.com/fuhuao/sw3518s_charger`**，类别选择 **集成**；
3. 添加后 HACS 商店即可搜索到 **SW3518S PD快充充电器**，点击安装；
4. **重启 Home Assistant**。

### 方式二：手动安装

将 `custom_components/sw3518s_charger/` 整个目录复制到 Home Assistant 的 `config/custom_components/` 下，然后重启 HA。

> 前置依赖：HA 中已配置好 **MQTT 集成**（Mosquitto broker 或其他 MQTT 服务器均可）。

---

## ⚙️ 配置

1. 设置 → 设备与服务 → **添加集成**；
2. 搜索 **SW3518S PD快充充电器**；
3. 填写 **MQTT 主题前缀**（默认 `home/sw3518s_charger`，需与 ESP32 固件一致）；
4. 完成。实体自动出现在设备「SW3518S PD快充充电器」下。

---

## 📊 实体列表

| 实体 | 类型 | 单位 | device_class |
|---|---|---|---|
| SW3518S 输出电压 | sensor | V | voltage |
| SW3518S C口电流 | sensor | A | current |
| SW3518S 输出功率 | sensor | W | power |
| SW3518S 芯片温度 | sensor | ℃ | temperature |
| SW3518S 协商快充协议 | sensor | — | — |
| SW3518S 快充输出总开关 | switch | — | — |
| SW3518S PD协议 | switch | — | — |
| SW3518S QC协议 | switch | — | — |
| SW3518S SCP协议 | switch | — | — |
| SW3518S VOOC协议 | switch | — | — |
| SW3518S FCP协议 | switch | — | — |

> 说明：「协商快充协议」为文本型 sensor（无单位），显示当前 PD/QC/SCP 等协议名称；协议开关用于启用/禁用对应快充协议，需固件实现 `set_proto` 指令。

---

## 🔄 更新

1. HACS → 商店 → **SW3518S PD快充充电器**；
2. 有新版时点 **更新**（HACS 会比较 GitHub Release tag）；
3. 更新完成后 **重启 Home Assistant**。

> 作者发布新版本流程：修改代码推送 GitHub → 创建新 Release（tag 递增，如 `v1.0.4`）→ HACS 即提示更新。

---

## 📜 更新日志

### v1.0.4（2026-09-15）

- 新增：PD / QC / SCP / VOOC / FCP 协议启用开关（`set_proto` 指令 + `proto_en` 状态回读）
- 新增：固件开发协议文档 `FIRMWARE_PROTOCOL.md`
- 修正：`codeowners` 改为 `@fuhuao`

### v1.0.3（2026-09-15）

- 修复：移除 `text_sensor` 平台（HA 2026.9 已移除内置 text_sensor 组件，协议实体并入 `sensor` 平台）
- 修复：实体改用平台标准基类 `SensorEntity` / `SwitchEntity`，确保状态正常显示
- 新增：「协商快充协议」传感器实体

### v1.0.2 / v1.0.1

- 接入 HACS 自定义仓库，完善 `hacs.json`（`content_in_root`）

---

## 🤖 自动化示例

```yaml
automation:
  - alias: "快充芯片超温保护"
    trigger:
      - platform: numeric_state
        entity_id: sensor.sw3518s_芯片温度   # 替换为你的实际实体 ID
        above: 70
    action:
      - service: switch.turn_off
        target:
          entity_id: switch.sw3518s_快充输出总开关  # 替换为你的实际实体 ID
      - service: notify.notify
        data:
          message: "SW3518S 快充芯片温度过高，已自动切断输出！"

  - alias: "充电开始提醒"
    trigger:
      - platform: state
        entity_id: switch.sw3518s_快充输出总开关
        to: "on"
    condition:
      - condition: numeric_state
        entity_id: sensor.sw3518s_输出功率
        above: 1
    action:
      - service: notify.notify
        data:
          message: "手机开始快充（功率 {{ states('sensor.sw3518s_输出功率') }} W）"
```

---

## ❓ 常见问题

| 问题 | 排查方向 |
|---|---|
| 添加集成时搜索不到 | 检查目录结构是否为 `config/custom_components/sw3518s_charger/`，`manifest.json` 中 domain 与文件夹名一致；查看 HA 日志 |
| 实体一直 unavailable | 确认 HA 已配置 MQTT；ESP32 是否在线；主题前缀是否一致 |
| 数值不更新 | 用 MQTT 工具（如 MQTT Explorer）订阅 `state` 主题，确认 ESP32 是否上报、JSON 字段名是否匹配 |
| 开关无法控制 | 确认 ESP32 订阅了 `cmd` 主题并实现 `output_on/off`、`set_proto` 解析 |
| 协议开关无效 | 确认 ESP32 固件实现了 `set_proto` 指令并在 `state` 上报 `proto_en`；不同充电器可能不支持全部协议 |
| 想指定 9V/12V/20V | 不支持。PD 电压由 SW3518S 硬件与手机协商决定 |

---

## ⚠️ 免责声明

本项目为 DIY 开源项目，涉及**高压（最高 20V）大电流（最大 5A）**电路。请确保电源、功率走线、散热设计合理，并做好绝缘防护。因使用不当造成的设备损坏或人身伤害，作者不承担任何责任。

---

## 📄 开源协议

MIT License

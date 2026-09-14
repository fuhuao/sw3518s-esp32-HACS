# SW3518S 固件端 MQTT 协议约定（Firmware Protocol）

> 本文件是 ESP32 固件开发时的**唯一权威约定**。固件只需按此文档实现 MQTT 收发，即可与 Home Assistant 集成（v1.0.4+）完整对接。
> 所有 JSON **字段名、协议 key、指令命令串**均大小写敏感，必须严格一致。

---

## 1. MQTT 连接信息

| 项 | 约定 |
|---|---|
| Broker | 与 Home Assistant 相同的 MQTT Broker（如 Mosquitto，默认 1883） |
| Client ID | 建议唯一，如 `esp32_sw3518s_01` |
| 主题前缀 `{prefix}` | 默认 `home/sw3518s_charger`，HA 添加集成时填写，**必须与固件一致** |
| QoS | 建议 `1`（至少一次） |
| Retain | 状态主题建议 `false`，命令主题 `false` |

---

## 2. 主题清单

| 主题 | 方向 | 用途 | 数据 |
|---|---|---|---|
| `{prefix}/state` | ESP32 → HA | 状态上报 | JSON（见 §3） |
| `{prefix}/cmd` | HA → ESP32 | 控制指令 | JSON（见 §4） |

示例（默认前缀）：

```
home/sw3518s_charger/state     # 发布状态
home/sw3518s_charger/cmd       # 订阅指令
```

---

## 3. 状态上报 `{prefix}/state`

### 3.1 完整示例

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

### 3.2 字段定义

| 字段 | 类型 | 单位 | 示例 | 必填 | 说明 |
|---|---|---|---|---|---|
| `vout_mv` | int | mV | `12120` | ✅ | 输出电压（毫伏），HA 会自动换算为 V |
| `iout_c_ma` | int | mA | `2450` | ✅ | C 口输出电流（毫安），HA 自动换算为 A |
| `power_w` | float | W | `29.69` | ✅ | 输出功率（瓦） |
| `temp_c` | float | ℃ | `47.5` | 推荐 | 芯片温度（摄氏度），缺失时该实体为 unknown |
| `proto_name` | string | — | `PD3.0-PPS` | 推荐 | 当前协商的快充协议名称（任意字符串，HA 原样显示） |
| `output_en` | bool | — | `true` | ✅ | 输出开关当前状态（**必须回读真实状态**，不能只报指令） |
| `proto_en` | object | — | 见下 | v1.0.4+ 推荐 | 各协议启用状态；缺失时 HA 协议开关保持默认值 |

### 3.3 `proto_en` 子字段（协议 key 对照表）

| 字段 | key（JSON 键） | 说明 | SW3518S 对应 |
|---|---|---|---|
| PD 协议 | `pd` | USB PD 2.0 / 3.0 / PPS | PD 使能位 |
| QC 协议 | `qc` | QC 2.0 / 3.0 / 4+ | QC 使能位 |
| SCP 协议 | `scp` | 华为超级快充 | SCP 使能位 |
| VOOC 协议 | `vooc` | OPPO 闪充 | VOOC 使能位 |
| FCP 协议 | `fcp` | 华为快充 | FCP 使能位 |

```json
"proto_en": {"pd": true, "qc": true, "scp": true, "vooc": true, "fcp": true}
```

> `proto_en` 缺失时：HA 端 5 个协议开关保持上次状态（首次为「开」），不影响其他功能。

### 3.4 上报时机与频率

- 建议**周期上报**（如每 1 秒）或**状态变化即上报**（推荐：变化上报 + 每 10s 心跳保活）；
- 上电后应**尽快发布一帧完整状态**，让 HA 实体立即有值；
- 执行 `cmd` 指令后，**下一帧 state 必须反映执行结果**（如 `output_en` 变化、`proto_en` 更新）。

---

## 4. 控制指令 `{prefix}/cmd`

固件需订阅 `{prefix}/cmd`，收到 JSON 后按 `cmd` 字段分发。

### 4.1 指令总表

| `cmd` 值 | 参数 | 含义 | 完整 JSON 示例 |
|---|---|---|---|
| `output_on` | 无 | 打开快充输出 | `{"cmd":"output_on"}` |
| `output_off` | 无 | 关闭快充输出 | `{"cmd":"output_off"}` |
| `set_proto` | `proto` + `enable` | 启用/禁用某快充协议 | `{"cmd":"set_proto","proto":"pd","enable":false}` |

### 4.2 指令逐条说明

**① 打开输出**

```json
{"cmd":"output_on"}
```

- 动作：置位 SW3518S 输出使能 → 下一帧 `"output_en": true`。

**② 关闭输出**

```json
{"cmd":"output_off"}
```

- 动作：复位输出使能 → 下一帧 `"output_en": false`。

**③ 设置协议使能**

```json
{"cmd":"set_proto","proto":"pd","enable":true}
{"cmd":"set_proto","proto":"qc","enable":false}
```

- `proto` 取值：`pd` / `qc` / `scp` / `vooc` / `fcp`（见 §3.3 对照表）；
- `enable`：`true` 启用，`false` 禁用；
- 动作：写 SW3518S 对应协议使能位 → 下一帧 `proto_en` 中对应 key 更新为实际结果；
- **未知 `proto` 或非法 `enable` 时应忽略并记日志，不要重启或清空状态。**

### 4.3 固件处理流程（伪代码）

```
on_message(topic, payload):
    if topic != cmd_topic: return
    try:
        msg = json.parse(payload)
    except:
        log("invalid json"); return

    switch msg.cmd:
        case "output_on":
            sw3518.set_output(true)
        case "output_off":
            sw3518.set_output(false)
        case "set_proto":
            proto = msg.proto
            enable = msg.enable
            if proto in ["pd","qc","scp","vooc","fcp"] and type(enable)==bool:
                sw3518.set_proto_enable(proto, enable)
            else:
                log("bad set_proto args")
        default:
            log("unknown cmd: " + msg.cmd)

publish_state():          # 变化时或每 1s
    state = {
        "vout_mv":  sw3518.read_vout_mv(),
        "iout_c_ma": sw3518.read_iout_ma(),
        "power_w":  sw3518.read_power_w(),
        "temp_c":   sw3518.read_temp_c(),
        "proto_name": sw3518.read_proto_name(),   # 如 "PD3.0-PPS"
        "output_en": sw3518.read_output_en(),     # 读真实状态
        "proto_en": {
            "pd": sw3518.read_proto_enable("pd"),
            "qc": sw3518.read_proto_enable("qc"),
            "scp": sw3518.read_proto_enable("scp"),
            "vooc": sw3518.read_proto_enable("vooc"),
            "fcp": sw3518.read_proto_enable("fcp"),
        },
    }
    mqtt.publish(state_topic, json.stringify(state), qos=1)
```

---

## 5. 协议名称 `proto_name` 建议取值

`proto_name` 为自由字符串，HA 原样显示。建议与充电器屏幕一致：

| 名称 | 含义 |
|---|---|
| `PD3.0-PPS` | PD 3.0 可编程电源 |
| `PD2.0` | PD 2.0 |
| `QC4+` / `QC3.0` / `QC2.0` | 高通 QC |
| `SCP` | 华为超级快充 |
| `VOOC` | OPPO 闪充 |
| `FCP` | 华为快充 |
| `NONE` / `NULL` | 无设备接入/未协商 |

---

## 6. 兼容性矩阵

| 集成版本 | state 必填 | proto_en | set_proto |
|---|---|---|---|
| v1.0.0 – v1.0.2 | vout_mv / iout_c_ma / power_w / output_en | 不支持 | 不支持 |
| v1.0.3 | 同上 | 可选（被忽略） | 不支持 |
| **v1.0.4（当前）** | 同上 | 推荐 | 支持 |

---

## 7. 常见错误排查（固件侧）

| 现象 | 固件侧检查点 |
|---|---|
| HA 实体 unavailable | ESP32 是否在线、是否订阅/发布到正确主题、前缀是否一致 |
| 数值不更新 | `state` 是否发布、JSON 是否能被解析、字段名是否拼写一致 |
| 开关点了没反应 | 是否订阅 `cmd`、指令 JSON 是否合法、SW3518S 使能位是否写入成功 |
| 协议开关状态不对 | `proto_en` 是否上报、key 是否与 §3.3 一致 |

---

## 8. 开发建议

- 使用 **ESP-IDF / Arduino + PubSubClient** 或 **ESPHome custom** 均可，协议与本文档解耦；
- SW3518S I2C 驱动可参考开源库 `h1_SW35xx`；
- 上报 JSON 用 `cJSON`（C）或 `ArduinoJson` 生成，避免手拼字符串出错；
- 上电先发一帧完整 state，再进入周期上报；
- 日志输出建议带时间戳，便于与 HA 侧对账。

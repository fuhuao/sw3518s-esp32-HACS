"""SW3518S 开关实体（快充输出总开关 + 协议启用开关，MQTT 下发指令给 ESP32）."""
from __future__ import annotations

import json
import logging

from homeassistant.components import mqtt
from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    DEVICE_MANUFACTURER,
    DEVICE_MODEL,
    DOMAIN,
    device_identifier,
    device_name,
    entity_unique_id,
)

_LOGGER = logging.getLogger(__name__)

# 支持的快充协议（key 用于 MQTT 指令与 state 上报，需与 ESP32 固件一致）
PROTOCOLS = [
    ("PD协议", "pd"),
    ("QC协议", "qc"),
    ("SCP协议", "scp"),
    ("VOOC协议", "vooc"),
    ("FCP协议", "fcp"),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """根据配置项建立开关实体."""
    prefix: str = entry.data["mqtt_topic_prefix"]
    state_topic = f"{prefix}/state"
    cmd_topic = f"{prefix}/cmd"
    switches = [
        SW3518Switch("快充输出总开关", "output_en", state_topic, cmd_topic, prefix)
    ]
    switches.extend(
        SW3518ProtoSwitch(name, key, state_topic, cmd_topic, prefix)
        for name, key in PROTOCOLS
    )
    async_add_entities(switches)


class SW3518Switch(SwitchEntity):
    """监听状态主题、通过命令主题控制 ESP32 输出开关."""

    _attr_should_poll = False

    def __init__(
        self, name: str, json_key: str, state_topic: str, cmd_topic: str, prefix: str
    ) -> None:
        self._attr_name = f"SW3518S {name}"
        self._json_key = json_key
        self._state_topic = state_topic
        self._cmd_topic = cmd_topic
        self._attr_is_on = False
        self._prefix = prefix
        self._attr_unique_id = entity_unique_id(prefix, "output_switch")

    @property
    def device_info(self):
        """归属到对应序号设备卡片（多模块自动区分）."""
        return {
            "identifiers": {device_identifier(self._prefix)},
            "name": device_name(self._prefix),
            "manufacturer": DEVICE_MANUFACTURER,
            "model": DEVICE_MODEL,
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await mqtt.async_subscribe(self.hass, self._state_topic, self._message_received)

    @callback
    def _message_received(self, msg):
        try:
            payload = json.loads(msg.payload)
        except (ValueError, TypeError):
            _LOGGER.warning("SW3518S 收到无效 JSON payload: %s", msg.payload)
            return
        if self._json_key in payload:
            self._attr_is_on = bool(payload[self._json_key])
            self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        """打开快充输出."""
        await mqtt.async_publish(self.hass, self._cmd_topic, '{"cmd":"output_on"}')

    async def async_turn_off(self, **kwargs):
        """关闭快充输出."""
        await mqtt.async_publish(self.hass, self._cmd_topic, '{"cmd":"output_off"}')


class SW3518ProtoSwitch(SwitchEntity):
    """快充协议启用/禁用开关，通过 MQTT 指令控制 ESP32 的 SW3518S 协议位."""

    _attr_should_poll = False

    def __init__(
        self, name: str, proto_key: str, state_topic: str, cmd_topic: str, prefix: str
    ) -> None:
        self._attr_name = f"SW3518S {name}"
        self._proto_key = proto_key
        self._state_topic = state_topic
        self._cmd_topic = cmd_topic
        self._attr_is_on = True  # 默认启用
        self._prefix = prefix
        self._attr_unique_id = entity_unique_id(prefix, f"proto_{proto_key}")

    @property
    def device_info(self):
        """归属到对应序号设备卡片（多模块自动区分）."""
        return {
            "identifiers": {device_identifier(self._prefix)},
            "name": device_name(self._prefix),
            "manufacturer": DEVICE_MANUFACTURER,
            "model": DEVICE_MODEL,
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        await mqtt.async_subscribe(self.hass, self._state_topic, self._message_received)

    @callback
    def _message_received(self, msg):
        try:
            payload = json.loads(msg.payload)
        except (ValueError, TypeError):
            _LOGGER.warning("SW3518S 收到无效 JSON payload: %s", msg.payload)
            return
        proto_en = payload.get("proto_en")
        if isinstance(proto_en, dict) and self._proto_key in proto_en:
            self._attr_is_on = bool(proto_en[self._proto_key])
            self.async_write_ha_state()

    async def async_turn_on(self, **kwargs):
        """启用该快充协议."""
        await mqtt.async_publish(
            self.hass, self._cmd_topic,
            json.dumps({"cmd": "set_proto", "proto": self._proto_key, "enable": True}),
        )

    async def async_turn_off(self, **kwargs):
        """禁用该快充协议."""
        await mqtt.async_publish(
            self.hass, self._cmd_topic,
            json.dumps({"cmd": "set_proto", "proto": self._proto_key, "enable": False}),
        )

"""SW3518S 散热风扇温度阈值 number 实体（MQTT 下发指令给 ESP32）."""
from __future__ import annotations

import json
import logging

from homeassistant.components import mqtt
from homeassistant.components.number import NumberEntity
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

# (显示名, state JSON键, set_fan 命令字段, 最小值, 最大值, 步长, 单位)
FAN_TEMPS = [
    ("风扇开启温度", "fan_on_temp", "on_temp", 30, 70, 1, "°C"),
    ("风扇停止温度", "fan_off_temp", "off_temp", 30, 70, 1, "°C"),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """根据配置项建立风扇温度 number 实体."""
    prefix: str = entry.data["mqtt_topic_prefix"]
    state_topic = f"{prefix}/state"
    cmd_topic = f"{prefix}/cmd"
    async_add_entities(
        SW3518FanNumber(name, json_key, cmd_key, lo, hi, step, unit, state_topic, cmd_topic, prefix)
        for name, json_key, cmd_key, lo, hi, step, unit in FAN_TEMPS
    )


class SW3518FanNumber(NumberEntity):
    """监听状态主题、通过命令主题设置风扇温度阈值."""

    _attr_should_poll = False

    def __init__(
        self,
        name: str,
        json_key: str,
        cmd_key: str,
        min_v: int,
        max_v: int,
        step: float,
        unit: str,
        state_topic: str,
        cmd_topic: str,
        prefix: str,
    ) -> None:
        self._attr_name = f"SW3518S {name}"
        self._json_key = json_key
        self._cmd_key = cmd_key
        self._state_topic = state_topic
        self._cmd_topic = cmd_topic
        self._prefix = prefix
        self._attr_native_min_value = min_v
        self._attr_native_max_value = max_v
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = unit
        self._attr_native_value = None
        self._attr_unique_id = entity_unique_id(prefix, f"fan_{json_key}")

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
            self._attr_native_value = float(payload[self._json_key])
            self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """设置温度阈值（只改本字段，不影响风扇开关状态）."""
        await mqtt.async_publish(
            self.hass,
            self._cmd_topic,
            json.dumps({"cmd": "set_fan", self._cmd_key: int(value)}),
        )
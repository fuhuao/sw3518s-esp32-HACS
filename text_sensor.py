"""SW3518S 文本传感器实体（当前协商的快充协议名称）."""
from __future__ import annotations

import json
import logging

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICE_MANUFACTURER, DEVICE_MODEL, DEVICE_NAME, DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """根据配置项建立文本传感器实体."""
    prefix: str = entry.data["mqtt_topic_prefix"]
    state_topic = f"{prefix}/state"
    async_add_entities(
        [SW3518TextSensor("协商快充协议", "proto_name", state_topic)]
    )


class SW3518TextSensor(Entity):
    """监听 MQTT JSON 状态主题的 SW3518S 文本传感器."""

    _attr_should_poll = False

    def __init__(self, name: str, json_key: str, state_topic: str) -> None:
        self._attr_name = f"SW3518S {name}"
        self._json_key = json_key
        self._state_topic = state_topic
        self._attr_native_value = None
        self._attr_unique_id = f"sw3518s_charger_{json_key}"

    @property
    def device_info(self):
        """统一归属到同一个设备卡片."""
        return {
            "identifiers": {(DOMAIN, "sw3518s_charger_01")},
            "name": DEVICE_NAME,
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
            self._attr_native_value = str(payload[self._json_key])
            self.async_write_ha_state()

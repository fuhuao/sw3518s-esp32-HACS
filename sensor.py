"""SW3518S 传感器实体（输出电压/电流/功率/芯片温度）."""
from __future__ import annotations

import json
import logging
from typing import Callable

from homeassistant.components import mqtt
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
    UnitOfTemperature,
)
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
    """根据配置项建立传感器实体."""
    prefix: str = entry.data["mqtt_topic_prefix"]
    state_topic = f"{prefix}/state"

    sensors = [
        SW3518Sensor(
            "输出电压", "vout_mv", UnitOfElectricPotential.VOLT,
            "voltage", state_topic, lambda v: float(v) / 1000,
        ),
        SW3518Sensor(
            "C口电流", "iout_c_ma", UnitOfElectricCurrent.AMPERE,
            "current", state_topic, lambda v: float(v) / 1000,
        ),
        SW3518Sensor(
            "输出功率", "power_w", UnitOfPower.WATT,
            "power", state_topic,
        ),
        SW3518Sensor(
            "芯片温度", "temp_c", UnitOfTemperature.CELSIUS,
            "temperature", state_topic,
        ),
    ]
    async_add_entities(sensors)


class SW3518Sensor(Entity):
    """监听 MQTT JSON 状态主题的 SW3518S 传感器."""

    _attr_should_poll = False

    def __init__(
        self,
        name: str,
        json_key: str,
        unit: str,
        device_class: str,
        state_topic: str,
        conv: Callable[[object], object] | None = None,
    ) -> None:
        self._attr_name = f"SW3518S {name}"
        self._json_key = json_key
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._state_topic = state_topic
        self._conv = conv or (lambda x: x)
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
        if self._json_key not in payload:
            return
        try:
            self._attr_native_value = self._conv(payload[self._json_key])
        except (TypeError, ValueError):
            self._attr_native_value = None
        self.async_write_ha_state()

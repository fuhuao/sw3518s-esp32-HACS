"""SW3518S PD快充充电器 HomeAssistant 集成入口."""
from __future__ import annotations

import logging

from homeassistant.components import mqtt
from homeassistant.config_entries import SOURCE_DISCOVERY, ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "switch"]

# hass.data[DOMAIN] 内部键（不会与 entry.entry_id 冲突）
_DISCOVERY_UNSUBS = "_discovery_unsubs"
_DISCOVERED = "_discovered_prefixes"


async def _create_entry_for_prefix(hass: HomeAssistant, prefix: str) -> None:
    """为自动发现的主题前缀创建一个新的配置项."""
    try:
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_DISCOVERY},
            data={"mqtt_topic_prefix": prefix},
        )
    except Exception:  # noqa: BLE001 - 防止发现流程异常影响 MQTT 回调
        _LOGGER.warning("SW3518S 自动创建配置项失败: prefix=%s", prefix, exc_info=True)


async def _start_discovery(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """订阅广播主题 {prefix}/+/state，自动发现新的 SW3518S 模块.

    多模块约定：模块 N 的主题前缀为 {prefix}/N（如 home/sw3518s_charger/2），
    其状态主题为 {prefix}/N/state。本集成监听 {prefix}/+/state，
    检测到未登记的前缀时自动创建对应的配置项。
    """
    prefix: str = entry.data["mqtt_topic_prefix"]
    discovery_topic = f"{prefix}/+/state"

    @callback
    async def _on_message(msg) -> None:
        topic: str = msg.topic
        # "home/sw3518s_charger/2/state" -> "home/sw3518s_charger/2"
        dev_prefix = topic.rsplit("/state", 1)[0]
        if not dev_prefix or dev_prefix == prefix:
            return
        # 已登记过的前缀（含正在创建中）直接忽略
        hass.data.setdefault(DOMAIN, {})
        marked = hass.data[DOMAIN].setdefault(_DISCOVERED, set())
        if dev_prefix in marked:
            return
        marked.add(dev_prefix)
        # 已存在同名配置项则忽略
        for existing in hass.config_entries.async_entries(DOMAIN):
            if existing.data.get("mqtt_topic_prefix") == dev_prefix:
                return
        _LOGGER.info("SW3518S 自动发现新模块: %s", dev_prefix)
        hass.async_create_task(_create_entry_for_prefix(hass, dev_prefix))

    unsub = await mqtt.async_subscribe(hass, discovery_topic, _on_message, qos=0)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(_DISCOVERY_UNSUBS, {})[entry.entry_id] = unsub


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """根据配置项设置集成."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # 每个配置项都承担一次自动发现监听（重复订阅幂等，无副作用）
    await _start_discovery(hass, entry)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """卸载集成."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        # 取消该配置项的发现订阅
        unsubs: dict = hass.data[DOMAIN].get(_DISCOVERY_UNSUBS, {})
        unsub = unsubs.pop(entry.entry_id, None)
        if unsub is not None:
            unsub()
    return unload_ok

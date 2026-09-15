"""SW3518S PD快充充电器 HomeAssistant 集成入口."""
from __future__ import annotations

import logging
import time

from homeassistant.components import mqtt
from homeassistant.config_entries import SOURCE_DISCOVERY, ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "switch"]

# hass.data[DOMAIN] 内部键（不会与 entry.entry_id 冲突）
_DISCOVERY_UNSUBS = "_discovery_unsubs"
_DISCOVERED = "_discovered_prefixes"
# 同一前缀的去重窗口（秒）：防止短时间内重复创建，超时后允许重新发现
_DEDUP_WINDOW = 30.0


def _base_prefix(prefix: str) -> str:
    """推导自动发现的基前缀.

    多模块约定：模块 N 的主题前缀为 {基前缀}/N（如 home/sw3518s_charger/2）。
    若配置前缀末尾是纯数字序号，则基前缀为其上一层；否则视为基前缀本身。
    """
    prefix = prefix.rstrip("/")
    parts = prefix.split("/")
    if len(parts) > 1 and parts[-1].isdigit():
        return "/".join(parts[:-1])
    return prefix


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
    """订阅广播主题 {基前缀}/+/state，自动发现新的 SW3518S 模块.

    多模块约定：模块 N 的主题前缀为 {基前缀}/N（如 home/sw3518s_charger/3），
    其状态主题为 {基前缀}/N/state。本集成监听 {基前缀}/+/state，
    检测到未登记的前缀时自动创建对应的配置项。
    无论配置项本身填的是基前缀还是带序号的 {基前缀}/N，都按基前缀监听，
    这样任意配置项都能发现所有兄弟模块（/1、/2、/3 …）。
    """
    prefix: str = entry.data["mqtt_topic_prefix"]
    discovery_topic = f"{_base_prefix(prefix)}/+/state"

    @callback
    async def _on_message(msg) -> None:
        topic: str = msg.topic
        # "home/sw3518s_charger/2/state" -> "home/sw3518s_charger/2"
        dev_prefix = topic.rsplit("/state", 1)[0]
        if not dev_prefix or dev_prefix == prefix:
            return
        hass.data.setdefault(DOMAIN, {})
        marked: dict = hass.data[DOMAIN].setdefault(_DISCOVERED, {})
        # 已存在同名配置项（手动添加或已自动创建）则忽略
        for existing in hass.config_entries.async_entries(DOMAIN):
            if existing.data.get("mqtt_topic_prefix") == dev_prefix:
                return
        # 同一前缀在去重窗口内只触发一次创建流程（防并发重复）；
        # 窗口过期后允许再次发现——配置项被删除后无需重启 HA 即可重新自动发现
        now = time.monotonic()
        if now - marked.get(dev_prefix, 0.0) < _DEDUP_WINDOW:
            return
        marked[dev_prefix] = now
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

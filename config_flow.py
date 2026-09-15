"""SW3518S 集成配置流（添加集成时的图形化弹窗）."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries

from .const import DEFAULT_MQTT_PREFIX, DOMAIN


def _device_suffix(prefix: str) -> str:
    """从前缀提取设备序号（如 home/sw3518s_charger/2 -> 2；默认前缀 -> 空串）."""
    tail = prefix.rstrip("/").rsplit("/", 1)[-1]
    return tail.removeprefix("sw3518s_charger").strip("_")


class SW3518SConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """SW3518S 快充充电器配置流."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """用户配置步骤：填写 MQTT 主题前缀."""
        errors = {}
        if user_input is not None:
            prefix = user_input["mqtt_topic_prefix"].strip().rstrip("/")
            if not prefix:
                errors["mqtt_topic_prefix"] = "不能为空"
            else:
                await self.async_set_unique_id(prefix)
                self._abort_if_unique_id_configured()
                suffix = _device_suffix(prefix)
                title = "SW3518S快充充电器" + (f"-{suffix}" if suffix else "")
                return self.async_create_entry(
                    title=title,
                    data={"mqtt_topic_prefix": prefix},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "mqtt_topic_prefix", default=DEFAULT_MQTT_PREFIX
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_discovery(self, discovery_info):
        """自动发现新模块：收到 {prefix}/N/state 广播后由入口创建."""
        prefix = str(discovery_info["mqtt_topic_prefix"]).strip().rstrip("/")
        await self.async_set_unique_id(prefix)
        self._abort_if_unique_id_configured()
        suffix = _device_suffix(prefix)
        return self.async_create_entry(
            title="SW3518S快充充电器" + (f"-{suffix}" if suffix else ""),
            data={"mqtt_topic_prefix": prefix},
        )

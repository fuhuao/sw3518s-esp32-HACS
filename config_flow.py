"""SW3518S 集成配置流（添加集成时的图形化弹窗）."""
from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries

from .const import DEFAULT_MQTT_PREFIX, DOMAIN


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
                return self.async_create_entry(
                    title="SW3518S快充充电器",
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

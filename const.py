"""SW3518S 集成常量与多设备辅助函数."""
DOMAIN = "sw3518s_charger"
DEFAULT_MQTT_PREFIX = "home/sw3518s_charger"

DEVICE_NAME = "SW3518S PD快充充电器"
DEVICE_MANUFACTURER = "ISMARTWARE"
DEVICE_MODEL = "SW3518S"


def _device_suffix(prefix: str) -> str:
    """从前缀提取设备序号（home/sw3518s_charger/2 -> '2'；默认前缀 -> ''）."""
    tail = prefix.rstrip("/").rsplit("/", 1)[-1]
    return tail.removeprefix("sw3518s_charger").strip("_")


def device_identifier(prefix: str) -> tuple[str, str]:
    """设备唯一标识：默认前缀保持旧版 sw3518s_charger_01，多模块按序号派生."""
    suffix = _device_suffix(prefix)
    return (DOMAIN, f"sw3518s_charger_{suffix or '01'}")


def device_name(prefix: str) -> str:
    """设备显示名：默认设备用原名，多模块带序号."""
    suffix = _device_suffix(prefix)
    return DEVICE_NAME if not suffix else f"{DEVICE_NAME}-{suffix}"


def entity_unique_id(prefix: str, kind: str) -> str:
    """实体唯一 ID：默认前缀保持旧版 sw3518s_charger_<kind>，多模块按序号派生."""
    suffix = _device_suffix(prefix)
    return f"sw3518s_charger{'_' + suffix if suffix else ''}_{kind}"

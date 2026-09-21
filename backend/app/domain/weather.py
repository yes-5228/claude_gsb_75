"""气象要素定义与相关分析领域规则."""

# 一次观测一个监测点 + 一个时刻 + 一个数据周期, 各要素为同一条记录上的字段
WEATHER_FACTORS = {
    "temperature": {
        "code": "temperature",
        "label": "温度",
        "unit": "℃",
        "precision": 1,
        "required": False,
        "min": -60.0,
        "max": 60.0,
        "correlatable": True,
        "description": "距地 1.5 m 气温",
    },
    "humidity": {
        "code": "humidity",
        "label": "相对湿度",
        "unit": "%",
        "precision": 0,
        "required": False,
        "min": 0.0,
        "max": 100.0,
        "correlatable": True,
        "description": "相对湿度",
    },
    "wind_speed": {
        "code": "wind_speed",
        "label": "风速",
        "unit": "m/s",
        "precision": 1,
        "required": False,
        "min": 0.0,
        "max": 75.0,
        "correlatable": True,
        "description": "距地 10 m 平均风速",
    },
    "wind_direction": {
        "code": "wind_direction",
        "label": "风向",
        "unit": "°",
        "precision": 0,
        "required": False,
        "min": 0.0,
        "max": 360.0,
        "correlatable": False,
        "description": "正北顺时针方位角, 静风记为 0°",
    },
    "pressure": {
        "code": "pressure",
        "label": "大气压",
        "unit": "hPa",
        "precision": 1,
        "required": False,
        "min": 600.0,
        "max": 1100.0,
        "correlatable": True,
        "description": "本站气压",
    },
    "precipitation": {
        "code": "precipitation",
        "label": "降水量",
        "unit": "mm",
        "precision": 1,
        "required": False,
        "min": 0.0,
        "max": 500.0,
        "correlatable": True,
        "description": "该周期内累计降水量",
    },
}

# 参与数值相关分析的要素 (风向为角度量, 走方位分组统计)
NUMERIC_FACTOR_CODES = tuple(
    code for code, meta in WEATHER_FACTORS.items() if meta["correlatable"]
)
WEATHER_FACTOR_CODES = tuple(WEATHER_FACTORS.keys())

# 风向玫瑰图的 8 个方位区间 (正北顺时针)
WIND_SECTORS = [
    {"key": "N", "label": "北风 N", "range": (337.5, 22.5)},
    {"key": "NE", "label": "东北风 NE", "range": (22.5, 67.5)},
    {"key": "E", "label": "东风 E", "range": (67.5, 112.5)},
    {"key": "SE", "label": "东南风 SE", "range": (112.5, 157.5)},
    {"key": "S", "label": "南风 S", "range": (157.5, 202.5)},
    {"key": "SW", "label": "西南风 SW", "range": (202.5, 247.5)},
    {"key": "W", "label": "西风 W", "range": (247.5, 292.5)},
    {"key": "NW", "label": "西北风 NW", "range": (292.5, 337.5)},
]
CALM_LABEL = "静风"
CALM_WIND_SPEED = 0.2  # m/s, 不超过该风速视为静风

# 相关系数强度分级
CORRELATION_MIN_SAMPLES = 3


def get_weather_factor(code):
    """Return the weather factor definition or None when unknown."""
    return WEATHER_FACTORS.get(str(code or "").lower())


def factor_options():
    """Serialisable list used by the frontend dropdowns."""
    return [dict(meta) for meta in WEATHER_FACTORS.values()]


def sector_of(degree):
    """Map an azimuth degree (0~360) to one of the 8 compass sectors."""
    if degree is None:
        return None
    degree = float(degree) % 360.0
    for sector in WIND_SECTORS:
        low, high = sector["range"]
        if low > high:  # N spans 337.5~360 and 0~22.5
            if degree >= low or degree < high:
                return sector
        elif low <= degree < high:
            return sector
    return WIND_SECTORS[0]


def pearson(xs, ys):
    """Pearson product-moment correlation coefficient for two numeric samples."""
    count = len(xs)
    if count != len(ys) or count == 0:
        return None
    mean_x = sum(xs) / count
    mean_y = sum(ys) / count
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x <= 0 or var_y <= 0:
        return None
    return cov / (var_x ** 0.5 * var_y ** 0.5)


def correlation_strength(r):
    """Descriptive bucket for an r value (absolute magnitude)."""
    if r is None:
        return "none"
    magnitude = abs(r)
    if magnitude < 0.3:
        return "negligible"
    if magnitude < 0.5:
        return "weak"
    if magnitude < 0.8:
        return "moderate"
    return "strong"

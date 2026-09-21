"""气象要素定义: 要素编码、量纲、合理范围与风向十六方位编码.

气象数据不参与 GB 3095 浓度限值判定, 仅记录观测值并与同期浓度做关联分析,
因此要素元数据与 ``domain/standards.py`` 中的污染因子分开维护。
"""

# 数值型(连续量)气象要素, 录入时按 [min, max] 做合理性校验
MET_FACTORS = {
    "temperature": {
        "code": "temperature",
        "label": "温度",
        "short_label": "气温",
        "unit": "℃",
        "precision": 1,
        "min": -60.0,
        "max": 60.0,
    },
    "humidity": {
        "code": "humidity",
        "label": "相对湿度",
        "short_label": "湿度",
        "unit": "%",
        "precision": 1,
        "min": 0.0,
        "max": 100.0,
    },
    "wind_speed": {
        "code": "wind_speed",
        "label": "风速",
        "short_label": "风速",
        "unit": "m/s",
        "precision": 1,
        "min": 0.0,
        "max": 75.0,
    },
    "pressure": {
        "code": "pressure",
        "label": "气压",
        "short_label": "气压",
        "unit": "hPa",
        "precision": 1,
        "min": 300.0,
        "max": 1100.0,
    },
    "precipitation": {
        "code": "precipitation",
        "label": "降水量",
        "short_label": "降水",
        "unit": "mm",
        "precision": 1,
        "min": 0.0,
        "max": 1000.0,
    },
}

# 风向单独处理: 角度(0~360) + 十六方位代码
WIND_DIRECTION_CODE = "wind_direction"
WIND_DIRECTION_LABEL = "风向"
WIND_DIRECTION_MIN = 0.0
WIND_DIRECTION_MAX = 360.0

# 静风阈值: 风速低于该值时风向记为静风(C), 不参与风向方位统计
CALM_WIND_SPEED = 0.2

# 参与 Pearson 相关分析的连续气象要素
NUMERIC_FACTOR_CODES = tuple(MET_FACTORS.keys())

# 全部录入字段(数值要素 + 风向角度)
ALL_FIELD_CODES = NUMERIC_FACTOR_CODES + (WIND_DIRECTION_CODE,)

# 十六方位: 起始角度为中心角 ±11.25°
WIND_DIR_16 = (
    ("N", 0.0, "北"),
    ("NNE", 22.5, "北东北"),
    ("NE", 45.0, "东北"),
    ("ENE", 67.5, "东东北"),
    ("E", 90.0, "东"),
    ("ESE", 112.5, "东东南"),
    ("SE", 135.0, "东南"),
    ("SSE", 157.5, "南东南"),
    ("S", 180.0, "南"),
    ("SSW", 202.5, "南西南"),
    ("SW", 225.0, "西南"),
    ("WSW", 247.5, "西西南"),
    ("W", 270.0, "西"),
    ("WNW", 292.5, "西西北"),
    ("NW", 315.0, "西北"),
    ("NNW", 337.5, "北西北"),
)

# 关联分析风向玫瑰按八方位归并
WIND_SECTORS_8 = (
    ("N", "北", (337.5, 22.5)),
    ("NE", "东北", (22.5, 67.5)),
    ("E", "东", (67.5, 112.5)),
    ("SE", "东南", (112.5, 157.5)),
    ("S", "南", (157.5, 202.5)),
    ("SW", "西南", (202.5, 247.5)),
    ("W", "西", (247.5, 292.5)),
    ("NW", "西北", (292.5, 337.5)),
)


def get_factor(code):
    """返回数值型气象要素定义, 风向/未知代码返回 None."""
    return MET_FACTORS.get(str(code or "").lower())


def wind_direction_code(angle, wind_speed=None):
    """把风向角度编码为十六方位代码; 静风返回 ``C``。

    角度按 22.5° 一档四舍五入到最近的方位中心, 360° 归零位。
    """
    if angle is None:
        return None
    if wind_speed is not None and wind_speed < CALM_WIND_SPEED:
        return "C"
    normalized = float(angle) % 360.0
    index = int((normalized + 11.25) // 22.5) % 16
    return WIND_DIR_16[index][0]


def wind_direction_label(code):
    """十六方位代码 / 静风 -> 中文名称。"""
    if code is None:
        return None
    if code == "C":
        return "静风"
    for item in WIND_DIR_16:
        if item[0] == code:
            return item[2]
    return code


def sector_of(angle):
    """把 0~360° 风向角度归入八方位, 返回方位代码."""
    if angle is None:
        return None
    normalized = float(angle) % 360.0
    for code, _label, (start, end) in WIND_SECTORS_8:
        if start > end:  # 北方位跨 0°
            if normalized >= start or normalized < end:
                return code
        elif start <= normalized < end:
            return code
    return "N"


def factor_options():
    """可序列化的要素清单(含风向), 供前端下拉与录入表单使用."""
    items = [dict(item) for item in MET_FACTORS.values()]
    items.append(
        {
            "code": WIND_DIRECTION_CODE,
            "label": WIND_DIRECTION_LABEL,
            "short_label": "风向",
            "unit": "°",
            "precision": 0,
            "min": WIND_DIRECTION_MIN,
            "max": WIND_DIRECTION_MAX,
        }
    )
    return items

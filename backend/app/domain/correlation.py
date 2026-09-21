"""气象要素与同期浓度的关联统计算法 (无第三方依赖)."""
import math

from .weather import WIND_DIRECTION_LABEL, WIND_SECTORS_8, sector_of

# Pearson 相关系数的经验强度划分(绝对值)
STRENGTH_RULES = (
    (0.8, "极强相关"),
    (0.6, "强相关"),
    (0.4, "中等相关"),
    (0.2, "弱相关"),
    (0.0, "极弱相关/不相关"),
)

# 计算相关系数所需的最少配对样本数
MIN_PAIRED_SAMPLES = 3


def strength_of(r):
    """按相关系数绝对值给出经验性强弱描述."""
    if r is None:
        return None
    magnitude = abs(r)
    for threshold, label in STRENGTH_RULES:
        if magnitude >= threshold:
            return label
    return STRENGTH_RULES[-1][1]


def pearson(xs, ys):
    """皮尔逊相关系数; 样本不足或方差为 0 时返回 None."""
    count = len(xs)
    if count < MIN_PAIRED_SAMPLES:
        return None
    mean_x = sum(xs) / count
    mean_y = sum(ys) / count
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x <= 0 or var_y <= 0:
        return None
    return cov / math.sqrt(var_x * var_y)


def numeric_correlation(samples, factor_code, factor_label, pollutant_label):
    """对一个连续气象要素计算与浓度的 Pearson 相关.

    samples: [{"factor": value|None, "value": concentration, ...}, ...]
    """
    paired = [
        item for item in samples
        if item.get(factor_code) is not None and item.get("value") is not None
    ]
    xs = [float(item[factor_code]) for item in paired]
    ys = [float(item["value"]) for item in paired]
    r = pearson(xs, ys)
    mean_factor = sum(xs) / len(xs) if xs else None
    mean_value = sum(ys) / len(ys) if ys else None
    return {
        "factor": factor_code,
        "factor_label": factor_label,
        "kind": "numeric",
        "pollutant_label": pollutant_label,
        "sample_count": len(paired),
        "pearson_r": round(r, 4) if r is not None else None,
        "strength": strength_of(r),
        "direction": _direction(r),
        "factor_avg": round(mean_factor, 2) if mean_factor is not None else None,
        "concentration_avg": round(mean_value, 2) if mean_value is not None else None,
        "enough_samples": len(paired) >= MIN_PAIRED_SAMPLES,
    }


def _direction(r):
    if r is None:
        return None
    if r > 0.02:
        return "正相关"
    if r < -0.02:
        return "负相关"
    return "近乎无关"


def wind_sector_stats(samples, pollutant_label):
    """按八方位统计平均浓度与样本占比, 并识别静风与主导风向.

    samples: [{"wind_direction": angle|None, "wind_speed": speed|None,
               "calm": bool, "value": concentration}, ...]
    """
    buckets = {code: {"code": code, "label": label, "values": []}
               for code, label, _span in WIND_SECTORS_8}
    calm_values = []
    used = 0
    total_concentration = 0.0

    for item in samples:
        angle = item.get("wind_direction")
        value = item.get("value")
        if value is None or angle is None:
            continue
        used += 1
        total_concentration += float(value)
        if item.get("calm"):
            calm_values.append(float(value))
            continue
        code = sector_of(angle)
        buckets[code]["values"].append(float(value))

    sectors = []
    for code, label, _span in WIND_SECTORS_8:
        values = buckets[code]["values"]
        sectors.append(
            {
                "code": code,
                "label": label,
                "count": len(values),
                "ratio": round(len(values) / used, 4) if used else 0.0,
                "avg_concentration": round(sum(values) / len(values), 2) if values else None,
                "max_concentration": round(max(values), 2) if values else None,
            }
        )

    prevailing = max(sectors, key=lambda item: item["count"]) if used else None
    enriched = {
        "factor": "wind_direction",
        "factor_label": WIND_DIRECTION_LABEL,
        "kind": "direction",
        "pollutant_label": pollutant_label,
        "sample_count": used,
        "sectors": sectors,
        "calm": {
            "count": len(calm_values),
            "ratio": round(len(calm_values) / used, 4) if used else 0.0,
            "avg_concentration": round(sum(calm_values) / len(calm_values), 2)
            if calm_values else None,
        },
        "prevailing_sector": prevailing["code"] if prevailing and prevailing["count"] else None,
        "prevailing_sector_label": prevailing["label"] if prevailing and prevailing["count"] else None,
        "overall_avg_concentration": round(total_concentration / used, 2) if used else None,
        "enough_samples": used >= MIN_PAIRED_SAMPLES,
    }
    return enriched

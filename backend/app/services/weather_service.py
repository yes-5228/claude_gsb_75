"""气象要素录入、查询与“气象-浓度”关联分析业务逻辑."""
from datetime import datetime, time

from sqlalchemy import func

from ..domain import correlation as correlation_stats
from ..domain.constants import PERIOD_LABELS
from ..domain.standards import POLLUTANT_CODES, get_pollutant
from ..domain.weather import (
    ALL_FIELD_CODES,
    CALM_WIND_SPEED,
    MET_FACTORS,
    NUMERIC_FACTOR_CODES,
    WIND_DIRECTION_CODE,
    WIND_DIRECTION_MAX,
    WIND_DIRECTION_MIN,
    get_factor,
    wind_direction_label,
)
from ..errors import ConflictError, NotFoundError, ValidationError
from ..extensions import db
from ..models import Measurement, Station, WeatherRecord
from ..models.base import iso
from ..utils.validation import parse_date

# 对照时序最多返回的配对点, 防止大范围查询拖垮前端图表
MAX_SERIES_POINTS = 300

FIELD_LABELS = {code: meta["label"] for code, meta in MET_FACTORS.items()}
FIELD_LABELS[WIND_DIRECTION_CODE] = "风向角度"


def _load_station(station_id):
    station = db.session.get(Station, station_id)
    if station is None:
        raise NotFoundError("监测点不存在: id=%s" % station_id)
    return station


def get_weather_record(record_id):
    record = db.session.get(WeatherRecord, record_id)
    if record is None:
        raise NotFoundError("气象记录不存在: id=%s" % record_id)
    return record


def _coerce_value(raw, factor_code):
    """把单个要素录入值转成 float; 空串/None 表示缺测."""
    if raw is None or str(raw).strip() == "":
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValidationError(
            "%s观测值必须为数字" % FIELD_LABELS[factor_code],
            fields={factor_code: "invalid_number"},
        )
    meta = get_factor(factor_code)
    if value < meta["min"] or value > meta["max"]:
        raise ValidationError(
            "%s观测值超出合理范围(%s ~ %s %s)"
            % (meta["label"], meta["min"], meta["max"], meta["unit"]),
            fields={factor_code: "out_of_range"},
        )
    return value


def _coerce_wind_direction(raw):
    if raw is None or str(raw).strip() == "":
        return None
    try:
        angle = float(raw)
    except (TypeError, ValueError):
        raise ValidationError("风向角度必须为数字", fields={WIND_DIRECTION_CODE: "invalid_number"})
    if angle < WIND_DIRECTION_MIN or angle > WIND_DIRECTION_MAX:
        raise ValidationError(
            "风向角度应在 %s ~ %s 度之间(0/360 为正北)"
            % (WIND_DIRECTION_MIN, WIND_DIRECTION_MAX),
            fields={WIND_DIRECTION_CODE: "out_of_range"},
        )
    return angle


def extract_fields(payload):
    """从请求体提取并校验各气象要素观测值."""
    values = {}
    for code in NUMERIC_FACTOR_CODES:
        if code in payload:
            values[code] = _coerce_value(payload.get(code), code)
    if WIND_DIRECTION_CODE in payload:
        values[WIND_DIRECTION_CODE] = _coerce_wind_direction(payload.get(WIND_DIRECTION_CODE))

    if not any(value is not None for value in values.values()):
        raise ValidationError("至少填写一个气象要素观测值", fields={"entries": "empty"})
    return values


def record_observation(station_id, measured_at, period, values, data_source="manual",
                       recorder=None, remark=None, overwrite=False):
    """写入某监测点某时刻的一组气象要素观测值."""
    station = _load_station(station_id)
    record = WeatherRecord.query.filter_by(
        station_id=station.id, period=period, measured_at=measured_at
    ).one_or_none()

    if record is not None and not overwrite:
        raise ConflictError(
            "该监测点 %s 时刻的气象记录已存在, 如需覆盖请勾选\"覆盖已有记录\""
            % measured_at.strftime("%Y-%m-%d %H:%M")
        )

    is_new = record is None
    if is_new:
        record = WeatherRecord(station_id=station.id, period=period, measured_at=measured_at)
        db.session.add(record)

    for code in ALL_FIELD_CODES:
        if code in values:
            setattr(record, code, values[code])
    record.data_source = data_source
    record.recorder = recorder
    record.remark = remark

    db.session.commit()
    payload = record.to_dict(include_station=True)
    return {
        "station": station.to_option(),
        "measured_at": iso(record.measured_at),
        "period": period,
        "created": [payload] if is_new else [],
        "updated": [] if is_new else [payload],
        "summary": {
            "created_count": 1 if is_new else 0,
            "updated_count": 0 if is_new else 1,
            "factor_count": len(record.observed_factors()),
        },
    }


def delete_weather_record(record):
    payload = record.to_dict()
    db.session.delete(record)
    db.session.commit()
    return payload


# ---------------------------------------------------------------- filtering
def _split(value):
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _date_bound(raw, end_of_day=False):
    if raw in (None, ""):
        return None
    parsed = parse_date(raw, "日期")
    return datetime.combine(parsed, time.max if end_of_day else time.min)


def parse_weather_filters(args):
    station_ids = []
    for item in _split(args.get("station_id")):
        try:
            station_ids.append(int(item))
        except ValueError:
            raise ValidationError("station_id 参数必须为整数", fields={"station_id": "invalid"})

    periods = _split(args.get("period"))
    for period in periods:
        if period not in PERIOD_LABELS:
            raise ValidationError("未知数据周期: %s" % period, fields={"period": "unknown"})

    factors = [item.lower() for item in _split(args.get("factor"))]
    for factor in factors:
        if factor not in ALL_FIELD_CODES:
            raise ValidationError("未知气象要素: %s" % factor, fields={"factor": "unknown"})

    date_from = _date_bound(args.get("date_from"))
    date_to = _date_bound(args.get("date_to"), end_of_day=True)
    if date_from and date_to and date_from > date_to:
        raise ValidationError("开始时间不能晚于结束时间", fields={"date_from": "range_invalid"})

    return {
        "station_ids": station_ids,
        "areas": _split(args.get("area")),
        "periods": periods,
        "factors": factors,
        "data_sources": _split(args.get("data_source")),
        "date_from": date_from,
        "date_to": date_to,
    }


def _apply_weather_filters(query, filters):
    query = query.join(Station, WeatherRecord.station_id == Station.id)
    if filters["station_ids"]:
        query = query.filter(WeatherRecord.station_id.in_(filters["station_ids"]))
    if filters["areas"]:
        query = query.filter(Station.area.in_(filters["areas"]))
    if filters["periods"]:
        query = query.filter(WeatherRecord.period.in_(filters["periods"]))
    if filters["data_sources"]:
        query = query.filter(WeatherRecord.data_source.in_(filters["data_sources"]))
    if filters["date_from"]:
        query = query.filter(WeatherRecord.measured_at >= filters["date_from"])
    if filters["date_to"]:
        query = query.filter(WeatherRecord.measured_at <= filters["date_to"])
    for factor in filters["factors"]:
        query = query.filter(getattr(WeatherRecord, factor).isnot(None))
    return query


def weather_query(args):
    filters = parse_weather_filters(args)
    query = _apply_weather_filters(db.session.query(WeatherRecord), filters)
    return query.order_by(WeatherRecord.measured_at.desc(), WeatherRecord.id.desc()), filters


def weather_summary(filters):
    total, stations, first_at, last_at = _apply_weather_filters(
        db.session.query(
            func.count(WeatherRecord.id),
            func.count(func.distinct(WeatherRecord.station_id)),
            func.min(WeatherRecord.measured_at),
            func.max(WeatherRecord.measured_at),
        ),
        filters,
    ).one()
    total = int(total or 0)
    coverage = (
        {code: _factor_coverage(code, filters) for code in ALL_FIELD_CODES} if total else {}
    )
    return {
        "total": total,
        "station_count": int(stations or 0),
        "first_measured_at": iso(first_at),
        "last_measured_at": iso(last_at),
        "factor_coverage": coverage,
    }


def _factor_coverage(code, filters):
    query = _apply_weather_filters(db.session.query(func.count(WeatherRecord.id)), filters)
    return int(query.filter(getattr(WeatherRecord, code).isnot(None)).scalar() or 0)


# ------------------------------------------------------------ correlation
def validate_correlation_args(args):
    pollutant = str(args.get("pollutant") or "PM25").upper()
    if pollutant not in POLLUTANT_CODES:
        raise ValidationError("未知监测因子: %s" % pollutant, fields={"pollutant": "unknown"})

    period = args.get("period") or "hourly"
    if period not in PERIOD_LABELS:
        raise ValidationError("未知数据周期: %s" % period, fields={"period": "unknown"})

    station_ids = []
    for item in _split(args.get("station_id")):
        try:
            station_ids.append(int(item))
        except ValueError:
            raise ValidationError("station_id 参数必须为整数", fields={"station_id": "invalid"})

    factor = str(args.get("factor") or "temperature").lower()
    if factor not in ALL_FIELD_CODES:
        raise ValidationError(
            "factor 仅支持: %s" % ", ".join(ALL_FIELD_CODES), fields={"factor": "unknown"}
        )

    date_from = _date_bound(args.get("date_from"))
    date_to = _date_bound(args.get("date_to"), end_of_day=True)
    if date_from and date_to and date_from > date_to:
        raise ValidationError("开始时间不能晚于结束时间", fields={"date_from": "range_invalid"})

    return {
        "pollutant": pollutant,
        "period": period,
        "station_ids": station_ids,
        "factor": factor,
        "date_from": date_from,
        "date_to": date_to,
    }


def _paired_base_query(params):
    """按(站点, 时刻)内连接浓度与气象记录的基础查询."""
    query = (
        db.session.query(
            Measurement.measured_at.label("measured_at"),
            Measurement.station_id.label("station_id"),
            Measurement.value.label("value"),
            WeatherRecord.temperature.label("temperature"),
            WeatherRecord.humidity.label("humidity"),
            WeatherRecord.wind_speed.label("wind_speed"),
            WeatherRecord.wind_direction.label("wind_direction"),
            WeatherRecord.pressure.label("pressure"),
            WeatherRecord.precipitation.label("precipitation"),
        )
        .join(
            WeatherRecord,
            db.and_(
                WeatherRecord.station_id == Measurement.station_id,
                WeatherRecord.measured_at == Measurement.measured_at,
                WeatherRecord.period == Measurement.period,
            ),
        )
        .filter(
            Measurement.pollutant == params["pollutant"],
            Measurement.period == params["period"],
            WeatherRecord.period == params["period"],
        )
    )
    if params["station_ids"]:
        query = query.filter(Measurement.station_id.in_(params["station_ids"]))
    if params["date_from"]:
        query = query.filter(Measurement.measured_at >= params["date_from"])
    if params["date_to"]:
        query = query.filter(Measurement.measured_at <= params["date_to"])
    return query


def correlation_analysis(args):
    """计算所选气象要素与某污染因子同期浓度的关联结果."""
    params = validate_correlation_args(args)
    rows = (
        _paired_base_query(params)
        .order_by(Measurement.measured_at.asc(), Measurement.station_id.asc())
        .all()
    )
    samples = [dict(row._mapping) for row in rows]
    for item in samples:
        item["calm"] = (
            item["wind_direction"] is not None
            and item["wind_speed"] is not None
            and item["wind_speed"] < CALM_WIND_SPEED
        )

    pollutant_meta = get_pollutant(params["pollutant"])
    factor = params["factor"]

    wind_result = correlation_stats.wind_sector_stats(samples, pollutant_meta["label"])
    if factor == WIND_DIRECTION_CODE:
        result = wind_result
    else:
        result = correlation_stats.numeric_correlation(
            samples, factor, MET_FACTORS[factor]["label"], pollutant_meta["label"]
        )

    # 各连续要素一次性给出相关系数, 前端“切换因子”时无需再次请求
    factor_ranking = [
        correlation_stats.numeric_correlation(samples, code, meta["label"], pollutant_meta["label"])
        for code, meta in MET_FACTORS.items()
    ]
    factor_ranking.sort(
        key=lambda item: item["pearson_r"] if item["pearson_r"] is not None else 0.0,
        reverse=True,
    )

    station_ids = {item["station_id"] for item in samples}
    station_names = (
        dict(db.session.query(Station.id, Station.name).filter(Station.id.in_(station_ids)).all())
        if station_ids else {}
    )

    series = []
    for item in samples[:MAX_SERIES_POINTS]:
        series.append(
            {
                "measured_at": iso(item["measured_at"]),
                "station_id": item["station_id"],
                "station_name": station_names.get(item["station_id"], ""),
                "pollutant_value": round(float(item["value"]), 3),
                "temperature": item["temperature"],
                "humidity": item["humidity"],
                "wind_speed": item["wind_speed"],
                "wind_direction": item["wind_direction"],
                "pressure": item["pressure"],
                "precipitation": item["precipitation"],
            }
        )

    return {
        "params": {
            "pollutant": params["pollutant"],
            "pollutant_label": pollutant_meta["label"],
            "pollutant_unit": pollutant_meta["unit"],
            "factor": factor,
            "factor_label": (
                "风向" if factor == WIND_DIRECTION_CODE else MET_FACTORS[factor]["label"]
            ),
            "factor_unit": "°" if factor == WIND_DIRECTION_CODE else MET_FACTORS[factor]["unit"],
            "period": params["period"],
            "period_label": PERIOD_LABELS[params["period"]],
            "station_ids": params["station_ids"],
            "date_from": params["date_from"].date().isoformat() if params["date_from"] else None,
            "date_to": params["date_to"].date().isoformat() if params["date_to"] else None,
        },
        "sample_total": len(samples),
        "result": result,
        "wind_result": wind_result,
        "factor_ranking": factor_ranking,
        "series": series,
        "series_truncated": len(samples) > MAX_SERIES_POINTS,
        "series_limit": MAX_SERIES_POINTS,
    }


def paired_rows_for_export(params):
    """导出用配对明细(不分页), 复用关联分析的过滤口径."""
    rows = _paired_base_query(params).order_by(
        Measurement.measured_at.asc(), Measurement.station_id.asc()
    ).all()
    station_map = dict(db.session.query(Station.id, Station.name).all())
    items = []
    for row in rows:
        data = dict(row._mapping)
        items.append(
            {
                "measured_at": data["measured_at"],
                "station_name": station_map.get(data["station_id"], ""),
                "pollutant_value": data["value"],
                "temperature": data["temperature"],
                "humidity": data["humidity"],
                "wind_speed": data["wind_speed"],
                "wind_direction": data["wind_direction"],
                "wind_dir_label": _wind_label(data["wind_direction"], data["wind_speed"]),
                "pressure": data["pressure"],
                "precipitation": data["precipitation"],
            }
        )
    return items, params


def _wind_label(angle, speed):
    from ..domain.weather import wind_direction_code

    if angle is None:
        return ""
    return wind_direction_label(wind_direction_code(angle, speed))

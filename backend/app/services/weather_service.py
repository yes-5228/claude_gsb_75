"""气象要素录入、查询与气象-浓度关联分析业务逻辑."""
from collections import OrderedDict
from datetime import datetime, time

from sqlalchemy import func

from ..domain.constants import CORRELATION_STRENGTH_LABELS, PERIOD_LABELS
from ..domain.standards import get_pollutant
from ..domain.weather import (
    CALM_LABEL,
    CALM_WIND_SPEED,
    CORRELATION_MIN_SAMPLES,
    WIND_SECTORS,
    WEATHER_FACTORS,
    correlation_strength,
    get_weather_factor,
    pearson,
    sector_of,
)
from ..errors import ConflictError, NotFoundError, ValidationError
from ..extensions import db
from ..models import Measurement, Station, WeatherRecord
from ..models.base import iso
from ..utils.validation import parse_date


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _split(value):
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def _int_list(args, name):
    values = []
    for item in _split(args.get(name)):
        try:
            values.append(int(item))
        except ValueError:
            raise ValidationError(
                "%s 参数必须为整数" % name, fields={name: "invalid_integer"}
            )
    return values


def _date_arg(args, name, end_of_day=False):
    raw = args.get(name)
    if raw in (None, ""):
        return None
    parsed = parse_date(raw, name)
    return datetime.combine(parsed, time.max if end_of_day else time.min)


def _factor_number(data, code):
    """Read a weather factor value from the payload; None means not provided."""
    raw = data.get(code)
    if raw is None or str(raw).strip() == "":
        return None
    meta = WEATHER_FACTORS[code]
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValidationError(
            "%s必须为数字" % meta["label"], fields={code: "invalid_number"}
        )
    if value < meta["min"] or value > meta["max"]:
        raise ValidationError(
            "%s应在 %s ~ %s %s 之间"
            % (meta["label"], _fmt(meta["min"]), _fmt(meta["max"]), meta["unit"]),
            fields={code: "out_of_range"},
        )
    return value


def _fmt(value):
    return ("%s" % value).rstrip("0").rstrip(".") if isinstance(value, float) else str(value)


def parse_weather_payload(data):
    """Validate and normalise the factor fields of an entry/preview payload."""
    cleaned = {}
    for code, meta in WEATHER_FACTORS.items():
        value = _factor_number(data, code)
        if value is not None:
            cleaned[code] = round(value, meta["precision"])
    if not cleaned:
        raise ValidationError(
            "至少需要填写一个气象要素", fields={"factors": "empty"}
        )
    return cleaned


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


# --------------------------------------------------------------------------
# entry
# --------------------------------------------------------------------------
def preview_entry(factors):
    """Dry-run: echo normalised factor values without writing (used by the form)."""
    return {
        "factors": [
            {
                "factor": code,
                "factor_label": WEATHER_FACTORS[code]["label"],
                "value": value,
                "unit": WEATHER_FACTORS[code]["unit"],
            }
            for code, value in factors.items()
        ],
        "summary": {"factor_count": len(factors)},
    }


def record_observation(station_id, measured_at, period, factors, data_source="manual",
                       recorder=None, remark=None, overwrite=False):
    """Persist one weather observation snapshot for a station at a given time."""
    station = _load_station(station_id)
    record = WeatherRecord.query.filter_by(
        station_id=station.id, period=period, measured_at=measured_at
    ).one_or_none()

    if record is not None and not overwrite:
        raise ConflictError(
            "该监测点在所选时刻已存在%s气象观测记录, 如需更新请勾选\"覆盖已有记录\""
            % PERIOD_LABELS.get(period, period)
        )

    is_new = record is None
    if is_new:
        record = WeatherRecord(
            station_id=station.id, period=period, measured_at=measured_at
        )
        db.session.add(record)

    for code, value in factors.items():
        setattr(record, code, value)
    record.data_source = data_source
    record.recorder = recorder
    record.remark = remark

    db.session.commit()
    return {
        "station": station.to_option(),
        "measured_at": iso(measured_at),
        "period": period,
        "action": "created" if is_new else "updated",
        "record": record.to_dict(include_station=True),
        "summary": {"factor_count": len(factors)},
    }


def delete_weather_record(record):
    payload = record.to_dict()
    db.session.delete(record)
    db.session.commit()
    return payload


# --------------------------------------------------------------------------
# list query
# --------------------------------------------------------------------------
def parse_filters(args):
    periods = _split(args.get("period"))
    for period in periods:
        if period not in PERIOD_LABELS:
            raise ValidationError("未知数据周期: %s" % period, fields={"period": "unknown"})

    data_sources = _split(args.get("data_source"))
    factors = [item.lower() for item in _split(args.get("factor"))]
    for factor in factors:
        if factor not in WEATHER_FACTORS:
            raise ValidationError(
                "未知气象要素: %s" % factor, fields={"factor": "unknown"}
            )

    filters = {
        "station_ids": _int_list(args, "station_id"),
        "areas": _split(args.get("area")),
        "periods": periods,
        "data_sources": data_sources,
        "factors": factors,
        "date_from": _date_arg(args, "date_from"),
        "date_to": _date_arg(args, "date_to", end_of_day=True),
        "keyword": (args.get("keyword") or "").strip(),
        "recorder": (args.get("recorder") or "").strip(),
    }
    if filters["date_from"] and filters["date_to"] and filters["date_from"] > filters["date_to"]:
        raise ValidationError("开始时间不能晚于结束时间", fields={"date_from": "range_invalid"})
    return filters


def apply_filters(query, filters):
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
    if filters["recorder"]:
        query = query.filter(WeatherRecord.recorder.like("%" + filters["recorder"] + "%"))
    if filters["keyword"]:
        like = "%" + filters["keyword"] + "%"
        query = query.filter(
            (Station.name.like(like)) | (Station.code.like(like)) | (Station.area.like(like))
        )
    for factor in filters["factors"]:
        query = query.filter(getattr(WeatherRecord, factor).isnot(None))
    return query


def weather_query(args):
    filters = parse_filters(args)
    query = apply_filters(db.session.query(WeatherRecord), filters)
    return query.order_by(WeatherRecord.measured_at.desc(), WeatherRecord.id.desc()), filters


def summary(filters):
    """Aggregate counters shown above the weather record table."""
    query = apply_filters(
        db.session.query(
            func.count(WeatherRecord.id),
            func.count(func.distinct(WeatherRecord.station_id)),
            func.min(WeatherRecord.measured_at),
            func.max(WeatherRecord.measured_at),
            func.avg(WeatherRecord.temperature),
            func.avg(WeatherRecord.humidity),
            func.avg(WeatherRecord.wind_speed),
        ),
        filters,
    )
    total, stations, first_at, last_at, avg_temp, avg_hum, avg_wind = query.one()
    total = int(total or 0)
    return {
        "total": total,
        "station_count": int(stations or 0),
        "first_measured_at": iso(first_at),
        "last_measured_at": iso(last_at),
        "avg_temperature": round(float(avg_temp), 1) if avg_temp is not None else None,
        "avg_humidity": round(float(avg_hum), 1) if avg_hum is not None else None,
        "avg_wind_speed": round(float(avg_wind), 2) if avg_wind is not None else None,
    }


# --------------------------------------------------------------------------
# correlation analysis
# --------------------------------------------------------------------------
def _resolve_station_filter(args):
    station_ids = _int_list(args, "station_id")
    areas = _split(args.get("area"))
    query = db.session.query(Station.id)
    if station_ids:
        query = query.filter(Station.id.in_(station_ids))
    if areas:
        query = query.filter(Station.area.in_(areas))
    return [row[0] for row in query.all()], station_ids, areas


def _base_pair_query(station_ids, period, date_from, date_to):
    query = (
        db.session.query(
            WeatherRecord.measured_at.label("measured_at"),
            WeatherRecord.station_id.label("station_id"),
            Measurement.pollutant.label("pollutant"),
        )
        .select_from(WeatherRecord)
        .join(
            Station,
            Station.id == WeatherRecord.station_id,
        )
        .join(
            Measurement,
            db.and_(
                Measurement.station_id == WeatherRecord.station_id,
                Measurement.measured_at == WeatherRecord.measured_at,
                Measurement.period == WeatherRecord.period,
            ),
        )
        .filter(WeatherRecord.period == period, Measurement.period == period)
    )
    if station_ids:
        query = query.filter(WeatherRecord.station_id.in_(station_ids))
    if date_from:
        query = query.filter(WeatherRecord.measured_at >= date_from)
    if date_to:
        query = query.filter(WeatherRecord.measured_at <= date_to)
    return query


def _series_stats(values):
    if not values:
        return {"count": 0, "avg": None, "min": None, "max": None}
    return {
        "count": len(values),
        "avg": round(sum(values) / len(values), 2),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
    }


def correlation_payload(args, limit):
    """Build the paired meteorology/concentration comparison payload."""
    station_ids, raw_station_ids, areas = _resolve_station_filter(args)

    period = args.get("period") or "hourly"
    if period not in PERIOD_LABELS:
        raise ValidationError("未知数据周期: %s" % period, fields={"period": "unknown"})

    pollutant = (args.get("pollutant") or "PM25").upper()
    pollutant_meta = get_pollutant(pollutant)
    if pollutant_meta is None:
        raise ValidationError("未知监测因子: %s" % pollutant, fields={"pollutant": "unknown"})

    weather_factor = (args.get("weather_factor") or "temperature").lower()
    factor_meta = get_weather_factor(weather_factor)
    if factor_meta is None:
        raise ValidationError(
            "未知气象要素: %s" % weather_factor, fields={"weather_factor": "unknown"}
        )

    date_from = _date_arg(args, "date_from")
    date_to = _date_arg(args, "date_to", end_of_day=True)
    if date_from and date_to and date_from > date_to:
        raise ValidationError("开始时间不能晚于结束时间", fields={"date_from": "range_invalid"})

    query = _base_pair_query(station_ids, period, date_from, date_to)
    query = (
        query.add_columns(
            getattr(WeatherRecord, weather_factor).label("weather_value"),
            Measurement.value.label("pollutant_value"),
        )
        .filter(Measurement.pollutant == pollutant)
        .filter(getattr(WeatherRecord, weather_factor).isnot(None))
        .order_by(WeatherRecord.measured_at.asc(), WeatherRecord.station_id.asc())
        .limit(limit)
    )
    rows = query.all()

    points = [
        {
            "measured_at": iso(row.measured_at),
            "station_id": row.station_id,
            "pollutant": row.pollutant_value,
            "weather": row.weather_value,
        }
        for row in rows
    ]

    # ---- Pearson r (numeric factors only) ----
    # 多站点混用时各点位浓度本底不同, 先按站点分别做 z-score 标准化再合并,
    # 避免"工业站始终偏高"之类的点位基线差异稀释气象-浓度的同期相关信号。
    correlation = None
    wind_breakdown = None
    if weather_factor == "wind_direction":
        wind_breakdown = _wind_breakdown(
            station_ids, period, pollutant, date_from, date_to, limit
        )
    else:
        correlation = _correlation_block(points)

    # ---- aligned time series (averaged across the selected stations) ----
    series, weather_stats, pollutant_stats = _aligned_series(points)

    return {
        "filters": {
            "station_ids": raw_station_ids,
            "areas": areas,
            "period": period,
            "pollutant": pollutant,
            "weather_factor": weather_factor,
            "date_from": args.get("date_from") or None,
            "date_to": args.get("date_to") or None,
        },
        "pollutant_meta": {
            "code": pollutant_meta["code"],
            "label": pollutant_meta["label"],
            "unit": pollutant_meta["unit"],
        },
        "weather_meta": {
            "code": factor_meta["code"],
            "label": factor_meta["label"],
            "unit": factor_meta["unit"],
            "correlatable": factor_meta["correlatable"],
        },
        "pair_count": len(points),
        "correlation": correlation,
        "wind_breakdown": wind_breakdown,
        "weather_stats": weather_stats,
        "pollutant_stats": pollutant_stats,
        "series": series,
        "points": points,
        "station_count_scope": len(station_ids),
    }


def _standardised_pairs(points):
    """Per-station z-scores for both series, then pooled for correlation.

    With a single station this is identical to correlating the raw values.
    Stations contributing a constant series (variance 0) are skipped.
    """
    groups = {}
    for point in points:
        groups.setdefault(point["station_id"], []).append(point)

    xs, ys = [], []
    used_stations = 0
    for station_points in groups.values():
        wx = [point["weather"] for point in station_points]
        cy = [point["pollutant"] for point in station_points]
        std_x = _std(wx)
        std_y = _std(cy)
        if std_x <= 0 or std_y <= 0:
            continue
        mean_x = sum(wx) / len(wx)
        mean_y = sum(cy) / len(cy)
        for point in station_points:
            xs.append((point["weather"] - mean_x) / std_x)
            ys.append((point["pollutant"] - mean_y) / std_y)
        used_stations += 1
    return xs, ys, used_stations


def _std(values):
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return (sum((value - mean) ** 2 for value in values) / len(values)) ** 0.5


def _correlation_block(points):
    raw_xs = [point["weather"] for point in points]
    raw_ys = [point["pollutant"] for point in points]
    station_count = len({point["station_id"] for point in points})
    if len(points) >= CORRELATION_MIN_SAMPLES and station_count >= 1:
        xs, ys, used_stations = _standardised_pairs(points)
        r = pearson(xs, ys) if len(points) >= CORRELATION_MIN_SAMPLES else None
    else:
        r = None
        used_stations = 0
    strength = correlation_strength(r)
    return {
        "pearson_r": round(r, 4) if r is not None else None,
        "strength": strength,
        "strength_label": CORRELATION_STRENGTH_LABELS.get(strength, strength),
        "direction": (
            "positive" if r is not None and r > 0
            else "negative" if r is not None and r < 0
            else "none"
        ),
        "sample_size": len(points),
        "min_samples": CORRELATION_MIN_SAMPLES,
        "station_count": station_count,
        "standardised": station_count > 1,
        "used_station_count": used_stations,
        "weather_stats": _series_stats(raw_xs),
        "pollutant_stats": _series_stats(raw_ys),
    }


def _aligned_series(points):
    """Average same-timestamp observations across stations for the trend chart."""
    buckets = OrderedDict()
    for point in sorted(points, key=lambda item: item["measured_at"]):
        bucket = buckets.setdefault(point["measured_at"], {"weather": [], "pollutant": []})
        bucket["weather"].append(point["weather"])
        bucket["pollutant"].append(point["pollutant"])

    series = []
    weather_values, pollutant_values = [], []
    for measured_at, bucket in buckets.items():
        weather_avg = sum(bucket["weather"]) / len(bucket["weather"])
        pollutant_avg = sum(bucket["pollutant"]) / len(bucket["pollutant"])
        series.append(
            {
                "measured_at": measured_at,
                "weather": round(weather_avg, 2),
                "pollutant": round(pollutant_avg, 2),
                "sample_count": len(bucket["weather"]),
            }
        )
        weather_values.extend(bucket["weather"])
        pollutant_values.extend(bucket["pollutant"])
    return series, _series_stats(weather_values), _series_stats(pollutant_values)


def _wind_breakdown(station_ids, period, pollutant, date_from, date_to, limit):
    """Mean pollutant concentration per compass sector (+ calm) for wind direction."""
    rows = (
        _base_pair_query(station_ids, period, date_from, date_to)
        .add_columns(
            WeatherRecord.wind_direction.label("wind_direction"),
            WeatherRecord.wind_speed.label("wind_speed"),
            Measurement.value.label("pollutant_value"),
        )
        .filter(Measurement.pollutant == pollutant)
        .filter(WeatherRecord.wind_direction.isnot(None))
        .limit(limit)
        .all()
    )
    groups = OrderedDict((sector["key"], {"label": sector["label"], "values": []})
                         for sector in WIND_SECTORS)
    calm = {"label": CALM_LABEL, "values": []}
    for row in rows:
        if row.wind_speed is not None and row.wind_speed <= CALM_WIND_SPEED:
            calm["values"].append(row.pollutant_value)
            continue
        sector = sector_of(row.wind_direction)
        if sector:
            groups[sector["key"]]["values"].append(row.pollutant_value)

    items = []
    for sector in WIND_SECTORS:
        values = groups[sector["key"]]["values"]
        items.append(
            {
                "key": sector["key"],
                "label": sector["label"],
                "count": len(values),
                "avg_pollutant": round(sum(values) / len(values), 2) if values else None,
            }
        )
    items.append(
        {
            "key": "calm",
            "label": calm["label"],
            "count": len(calm["values"]),
            "avg_pollutant": round(sum(calm["values"]) / len(calm["values"]), 2)
            if calm["values"]
            else None,
        }
    )
    total = sum(item["count"] for item in items)
    return {
        "items": items,
        "total": total,
        "note": "风向为角度量, 不适用线性相关系数, 改按 8 方位 + 静风统计平均浓度",
    }


def paired_rows_for_export(args, limit):
    """Flat paired rows used by the analysis CSV export."""
    period = args.get("period") or "hourly"
    pollutant = (args.get("pollutant") or "PM25").upper()
    weather_factor = (args.get("weather_factor") or "temperature").lower()
    station_ids, _, _ = _resolve_station_filter(args)
    date_from = _date_arg(args, "date_from")
    date_to = _date_arg(args, "date_to", end_of_day=True)

    rows = (
        _base_pair_query(station_ids, period, date_from, date_to)
        .add_columns(
            Station.code.label("station_code"),
            Station.name.label("station_name"),
            Station.area.label("area"),
            getattr(WeatherRecord, weather_factor).label("weather_value"),
            Measurement.value.label("pollutant_value"),
            Measurement.unit.label("pollutant_unit"),
        )
        .filter(Measurement.pollutant == pollutant)
        .filter(getattr(WeatherRecord, weather_factor).isnot(None))
        .order_by(WeatherRecord.measured_at.asc())
        .limit(limit)
        .all()
    )
    return rows, weather_factor, pollutant

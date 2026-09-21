"""气象要素记录与关联分析 API."""
from flask import Blueprint, current_app, request

from ..domain.constants import DATA_SOURCE_LABELS, PERIOD_LABELS
from ..domain.standards import POLLUTANTS
from ..domain.weather import WEATHER_FACTORS, factor_options
from ..services import station_service, weather_service
from ..utils.pagination import paginate_query
from ..utils.validation import Validator
from .helpers import json_payload

bp = Blueprint("weather", __name__)


@bp.get("/", strict_slashes=False)
def list_weather():
    query, filters = weather_service.weather_query(request.args)
    result = paginate_query(query, lambda row: row.to_dict(include_station=True))
    result["summary"] = weather_service.summary(filters)
    return result


@bp.get("/summary")
def weather_summary():
    return weather_service.summary(weather_service.parse_filters(request.args))


@bp.get("/options")
def weather_options():
    """Options needed by the entry form and the analysis filters."""
    return {
        "stations": station_service.option_list(),
        "areas": station_service.area_list(),
        "factors": factor_options(),
        "pollutants": [
            {"value": code, "label": meta["label"], "unit": meta["unit"]}
            for code, meta in POLLUTANTS.items()
        ],
        "periods": [{"value": key, "label": label} for key, label in PERIOD_LABELS.items()],
        "data_sources": [
            {"value": key, "label": label} for key, label in DATA_SOURCE_LABELS.items()
        ],
    }


@bp.post("/preview")
def preview():
    """干跑校验: 录入表单实时回显规范化后的气象要素, 不写库."""
    data = json_payload()
    factors = weather_service.parse_weather_payload(data)
    return weather_service.preview_entry(factors)


@bp.post("/observations")
def create_observation():
    """一次录入某个监测点在同一时刻的一组气象要素."""
    data = json_payload()
    validator = Validator(data)
    station_id = validator.number("station_id", "监测点", required=True, minimum=1)
    measured_at = validator.datetime_field("measured_at", "观测时间", required=True)
    period = validator.choice("period", "数据周期", choices=tuple(PERIOD_LABELS.keys()),
                              required=True, default="hourly")
    data_source = validator.choice("data_source", "数据来源",
                                   choices=tuple(DATA_SOURCE_LABELS.keys()),
                                   required=False, default="manual")
    recorder = validator.text("recorder", "录入人", required=False, max_length=64)
    remark = validator.text("remark", "备注", required=False, max_length=500)
    overwrite = validator.boolean("overwrite", False)
    validator.raise_if_invalid("录入信息不合法")

    factors = weather_service.parse_weather_payload(data)
    return weather_service.record_observation(
        station_id=int(station_id),
        measured_at=measured_at,
        period=period,
        factors=factors,
        data_source=data_source or "manual",
        recorder=recorder,
        remark=remark,
        overwrite=bool(overwrite),
    ), 201


@bp.get("/export")
def export_weather():
    from ..utils.csv_export import csv_response

    query, _ = weather_service.weather_query(request.args)
    rows = query.limit(current_app.config["MAX_EXPORT_ROWS"]).all()

    def sector_label(row):
        from ..domain.weather import sector_of

        sector = sector_of(row.wind_direction)
        return sector["label"] if sector else ""

    columns = [
        ("站点编码", lambda row: row.station.code if row.station else ""),
        ("站点名称", lambda row: row.station.name if row.station else ""),
        ("所属区域", lambda row: row.station.area if row.station else ""),
        ("数据周期", lambda row: PERIOD_LABELS.get(row.period, row.period)),
        ("温度(℃)", "temperature"),
        ("相对湿度(%)", "humidity"),
        ("风速(m/s)", "wind_speed"),
        ("风向(°)", "wind_direction"),
        ("主导风向", sector_label),
        ("大气压(hPa)", "pressure"),
        ("降水量(mm)", "precipitation"),
        ("观测时间", lambda row: row.measured_at.strftime("%Y-%m-%d %H:%M")),
        ("数据来源", lambda row: DATA_SOURCE_LABELS.get(row.data_source, row.data_source)),
        ("录入人", "recorder"),
        ("备注", "remark"),
    ]
    return csv_response(rows, columns, "weather_records")


@bp.get("/correlation")
def correlation():
    """同期气象要素与污染浓度的对照与相关分析."""
    return weather_service.correlation_payload(
        request.args, current_app.config["MAX_CORRELATION_POINTS"]
    )


@bp.get("/correlation/export")
def correlation_export():
    """导出参与对照分析的成对样本."""
    from ..utils.csv_export import csv_response

    rows, weather_factor, pollutant = weather_service.paired_rows_for_export(
        request.args, current_app.config["MAX_CORRELATION_POINTS"]
    )
    weather_meta = WEATHER_FACTORS[weather_factor]
    pollutant_meta = POLLUTANTS[pollutant]
    columns = [
        ("观测时间", lambda row: row.measured_at.strftime("%Y-%m-%d %H:%M")),
        ("站点编码", "station_code"),
        ("站点名称", "station_name"),
        ("所属区域", "area"),
        ("%s(%s)" % (weather_meta["label"], weather_meta["unit"]), "weather_value"),
        ("%s(%s)" % (pollutant_meta["label"], pollutant_meta["unit"]), "pollutant_value"),
    ]
    return csv_response(rows, columns, "weather_correlation_%s_%s" % (weather_factor, pollutant))


@bp.get("/<int:record_id>")
def get_weather(record_id):
    return weather_service.get_weather_record(record_id).to_dict(include_station=True)


@bp.delete("/<int:record_id>")
def delete_weather(record_id):
    record = weather_service.get_weather_record(record_id)
    weather_service.delete_weather_record(record)
    return {"id": record_id, "deleted": True}

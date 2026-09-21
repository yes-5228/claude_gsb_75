"""气象要素记录与关联分析 API."""
from flask import Blueprint, current_app, request

from ..domain.constants import DATA_SOURCE_LABELS, PERIOD_LABELS
from ..domain.weather import factor_options
from ..services import station_service, weather_service
from ..utils.csv_export import csv_response
from ..utils.pagination import paginate_query
from ..utils.validation import Validator
from .helpers import json_payload

bp = Blueprint("weather", __name__)


@bp.get("/context")
def entry_context():
    """录入表单所需选项一次取回."""
    return {
        "stations": station_service.option_list(),
        "factors": factor_options(),
        "periods": [{"value": key, "label": label} for key, label in PERIOD_LABELS.items()],
        "data_sources": [
            {"value": key, "label": label} for key, label in DATA_SOURCE_LABELS.items()
        ],
    }


@bp.get("/factors")
def factors():
    return {"items": factor_options()}


@bp.get("/", strict_slashes=False)
def list_records():
    query, filters = weather_service.weather_query(request.args)
    result = paginate_query(query, lambda row: row.to_dict(include_station=True))
    result["summary"] = weather_service.weather_summary(filters)
    return result


@bp.get("/summary")
def records_summary():
    return weather_service.weather_summary(weather_service.parse_weather_filters(request.args))


@bp.post("/entries")
def create_entry():
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

    values = weather_service.extract_fields(data)
    return weather_service.record_observation(
        station_id=int(station_id),
        measured_at=measured_at,
        period=period,
        values=values,
        data_source=data_source or "manual",
        recorder=recorder,
        remark=remark,
        overwrite=bool(overwrite),
    ), 201


@bp.get("/correlation")
def correlation():
    """气象要素与同期浓度的关联分析(可按点位/时间范围/因子切换)."""
    return weather_service.correlation_analysis(request.args)


@bp.get("/export")
def export_records():
    """按筛选条件导出气象记录 CSV."""
    query, _ = weather_service.weather_query(request.args)
    rows = query.limit(current_app.config["MAX_EXPORT_ROWS"]).all()
    columns = [
        ("站点编码", lambda row: row.station.code if row.station else ""),
        ("站点名称", lambda row: row.station.name if row.station else ""),
        ("所属区域", lambda row: row.station.area if row.station else ""),
        ("观测时间", lambda row: row.measured_at.strftime("%Y-%m-%d %H:%M")),
        ("数据周期", lambda row: PERIOD_LABELS.get(row.period, row.period)),
        ("温度(℃)", "temperature"),
        ("相对湿度(%)", "humidity"),
        ("风速(m/s)", "wind_speed"),
        ("风向角度(°)", "wind_direction"),
        ("风向方位", lambda row: row.wind_dir_label or ""),
        ("气压(hPa)", "pressure"),
        ("降水量(mm)", "precipitation"),
        ("数据来源", lambda row: DATA_SOURCE_LABELS.get(row.data_source, row.data_source)),
        ("录入人", "recorder"),
        ("备注", "remark"),
    ]
    return csv_response(rows, columns, "weather_records")


@bp.get("/correlation/export")
def export_correlation():
    """导出关联分析所用的“浓度-气象要素”同期配对明细 CSV."""
    params = weather_service.validate_correlation_args(request.args)
    items, params = weather_service.paired_rows_for_export(params)
    from ..domain.standards import get_pollutant

    meta = get_pollutant(params["pollutant"])
    columns = [
        ("观测时间", lambda item: item["measured_at"].strftime("%Y-%m-%d %H:%M")),
        ("监测点", "station_name"),
        ("%s浓度(%s)" % (meta["label"], meta["unit"]), "pollutant_value"),
        ("温度(℃)", "temperature"),
        ("相对湿度(%)", "humidity"),
        ("风速(m/s)", "wind_speed"),
        ("风向角度(°)", "wind_direction"),
        ("风向方位", "wind_dir_label"),
        ("气压(hPa)", "pressure"),
        ("降水量(mm)", "precipitation"),
    ]
    return csv_response(items[: current_app.config["MAX_EXPORT_ROWS"]], columns,
                        "weather_correlation")


@bp.get("/<int:record_id>")
def get_record(record_id):
    return weather_service.get_weather_record(record_id).to_dict(include_station=True)


@bp.delete("/<int:record_id>")
def delete_record(record_id):
    record = weather_service.get_weather_record(record_id)
    weather_service.delete_weather_record(record)
    return {"id": record_id, "deleted": True}

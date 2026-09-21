"""气象要素录入 / 查询 / 关联分析接口测试."""
from datetime import datetime

import pytest

from app.domain.weather import pearson, sector_of
from app.models import WeatherRecord
from app.services import weather_service

WEATHER_HOURLY = {
    "temperature": 28.0,
    "humidity": 70.0,
    "wind_speed": 2.0,
    "wind_direction": 135.0,
    "pressure": 1008.0,
    "precipitation": 0.0,
}


def _weather_payload(station_id, measured_at="2026-09-01 10:00", period="hourly", **overrides):
    payload = {
        "station_id": station_id,
        "measured_at": measured_at,
        "period": period,
        "data_source": "manual",
        "recorder": "气象员",
        **WEATHER_HOURLY,
    }
    payload.update(overrides)
    return payload


# --------------------------------------------------------------------------
# domain helpers
# --------------------------------------------------------------------------
def test_sector_of_maps_azimuth_to_eight_compass_sectors():
    assert sector_of(0)["key"] == "N"
    assert sector_of(350)["key"] == "N"
    assert sector_of(45)["key"] == "NE"
    assert sector_of(90)["key"] == "E"
    assert sector_of(180)["key"] == "S"
    assert sector_of(270)["key"] == "W"
    assert sector_of(315)["key"] == "NW"


def test_pearson_perfect_and_inverse_linear_relation():
    xs = [1, 2, 3, 4, 5]
    assert pearson(xs, [2 * x + 1 for x in xs]) == pytest.approx(1.0, abs=1e-9)
    assert pearson(xs, [-x for x in xs]) == pytest.approx(-1.0, abs=1e-9)
    assert pearson([1, 1, 1], [1, 2, 3]) is None
    assert pearson([], []) is None


# --------------------------------------------------------------------------
# entry API
# --------------------------------------------------------------------------
def test_create_weather_observation(client, station):
    response = client.post("/api/weather/observations", json=_weather_payload(station.id))
    assert response.status_code == 201
    body = response.get_json()
    assert body["action"] == "created"
    assert body["summary"]["factor_count"] == 6
    record = body["record"]
    assert record["temperature"] == 28.0
    assert record["wind_direction"] == 135.0
    assert record["period_label"] == "小时均值"
    assert record["station"]["code"] == "TEST-001"

    stored = WeatherRecord.query.one()
    assert stored.humidity == 70.0
    assert stored.recorder == "气象员"


def test_duplicate_observation_conflicts_unless_overwrite(client, station):
    payload = _weather_payload(station.id)
    assert client.post("/api/weather/observations", json=payload).status_code == 201

    duplicate = client.post("/api/weather/observations", json=payload)
    assert duplicate.status_code == 409
    assert "覆盖已有记录" in duplicate.get_json()["error"]["message"]
    assert WeatherRecord.query.count() == 1

    payload["temperature"] = 31.2
    payload["overwrite"] = True
    overwritten = client.post("/api/weather/observations", json=payload)
    assert overwritten.status_code == 201
    assert overwritten.get_json()["action"] == "updated"
    assert WeatherRecord.query.count() == 1
    assert WeatherRecord.query.one().temperature == 31.2


def test_weather_entry_validation(client, station):
    # 监测点不存在
    response = client.post(
        "/api/weather/observations", json=_weather_payload(99999)
    )
    assert response.status_code == 404

    # 所有要素都为空
    empty = _weather_payload(station.id)
    for factor in ("temperature", "humidity", "wind_speed", "wind_direction",
                   "pressure", "precipitation"):
        empty[factor] = None
    assert client.post("/api/weather/observations", json=empty).status_code == 422

    # 湿度超出 0~100
    invalid = _weather_payload(station.id, humidity=120)
    body = client.post("/api/weather/observations", json=invalid)
    assert body.status_code == 422
    assert "humidity" in body.get_json()["error"]["fields"]


def test_weather_preview_does_not_write(client, station):
    response = client.post(
        "/api/weather/preview", json={"temperature": 25.0, "humidity": "60"}
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["summary"]["factor_count"] == 2
    assert body["factors"][0]["unit"] == "℃"
    assert WeatherRecord.query.count() == 0


def test_delete_weather_record(client, station):
    created = client.post(
        "/api/weather/observations", json=_weather_payload(station.id)
    ).get_json()
    record_id = created["record"]["id"]
    response = client.delete("/api/weather/%d" % record_id)
    assert response.status_code == 200
    assert WeatherRecord.query.count() == 0


# --------------------------------------------------------------------------
# list / filters / summary
# --------------------------------------------------------------------------
def test_weather_list_filters_and_summary(client, station, second_station):
    client.post("/api/weather/observations", json=_weather_payload(
        station.id, measured_at="2026-09-01 10:00", temperature=26.0, humidity=80.0))
    client.post("/api/weather/observations", json=_weather_payload(
        station.id, measured_at="2026-09-02 10:00",
        period="daily", temperature=30.0, humidity=60.0, wind_direction=None))
    client.post("/api/weather/observations", json=_weather_payload(
        second_station.id, measured_at="2026-09-01 10:00", temperature=24.0))

    response = client.get("/api/weather/?period=hourly")
    assert response.status_code == 200
    body = response.get_json()
    assert body["total"] == 2
    assert body["summary"]["station_count"] == 2
    assert body["summary"]["avg_temperature"] == 25.0

    only_station = client.get(
        "/api/weather/?station_id=%d&factor=wind_direction" % second_station.id
    ).get_json()
    assert only_station["total"] == 1


# --------------------------------------------------------------------------
# correlation analysis
# --------------------------------------------------------------------------
def _seed_paired_series(client, station):
    """Build paired weather/measurement data with a positive temp-O3 relation."""
    pairs = [
        ("2026-09-01 08:00", 24.0, 90.0),
        ("2026-09-01 14:00", 30.0, 150.0),
        ("2026-09-02 08:00", 25.0, 100.0),
        ("2026-09-02 14:00", 32.0, 170.0),
        ("2026-09-03 08:00", 23.0, 85.0),
    ]
    for measured_at, temp, o3 in pairs:
        client.post(
            "/api/weather/observations",
            json=_weather_payload(station.id, measured_at=measured_at, temperature=temp),
        )
        client.post(
            "/api/measurements/entries",
            json={
                "station_id": station.id,
                "measured_at": measured_at,
                "period": "hourly",
                "entries": [{"pollutant": "O3", "value": o3}],
            },
        )


def test_correlation_pairs_same_station_time_and_period(client, station, second_station):
    _seed_paired_series(client, station)
    # 另一监测点同时刻数据不应被错配进来
    client.post(
        "/api/measurements/entries",
        json={
            "station_id": second_station.id,
            "measured_at": "2026-09-01 14:00",
            "period": "hourly",
            "entries": [{"pollutant": "O3", "value": 300.0}],
        },
    )

    response = client.get(
        "/api/weather/correlation?station_id=%d&pollutant=O3&weather_factor=temperature"
        % station.id
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["pair_count"] == 5
    assert body["correlation"]["sample_size"] == 5
    assert body["correlation"]["pearson_r"] == pytest.approx(0.9988, abs=1e-3)
    assert body["correlation"]["direction"] == "positive"
    assert body["correlation"]["strength"] == "strong"
    # 五个时刻互不相同, 每个时刻一个样本
    assert len(body["series"]) == 5
    assert len({point["measured_at"] for point in body["points"]}) == 5


def test_correlation_requires_enough_samples(client, station):
    client.post(
        "/api/weather/observations",
        json=_weather_payload(station.id, temperature=28.0),
    )
    client.post(
        "/api/measurements/entries",
        json={
            "station_id": station.id,
            "measured_at": "2026-09-01 10:00",
            "period": "hourly",
            "entries": [{"pollutant": "PM25", "value": 50.0}],
        },
    )
    body = client.get(
        "/api/weather/correlation?station_id=%d" % station.id
    ).get_json()
    assert body["pair_count"] == 1
    assert body["correlation"]["pearson_r"] is None
    assert body["correlation"]["strength"] == "none"


def test_correlation_wind_direction_returns_sector_breakdown(client, station):
    for measured_at, direction in [
        ("2026-09-01 08:00", 30.0),
        ("2026-09-01 14:00", 180.0),
        ("2026-09-02 08:00", 200.0),
    ]:
        client.post(
            "/api/weather/observations",
            json=_weather_payload(station.id, measured_at=measured_at,
                                  wind_direction=direction, wind_speed=2.5),
        )
        client.post(
            "/api/measurements/entries",
            json={
                "station_id": station.id,
                "measured_at": measured_at,
                "period": "hourly",
                "entries": [{"pollutant": "PM25", "value": 40.0 if direction < 90 else 70.0}],
            },
        )
    response = client.get(
        "/api/weather/correlation?station_id=%d&weather_factor=wind_direction" % station.id
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["correlation"] is None
    breakdown = body["wind_breakdown"]
    assert breakdown["total"] == 3
    by_key = {item["key"]: item for item in breakdown["items"]}
    assert by_key["NE"]["count"] == 1
    assert by_key["NE"]["avg_pollutant"] == 40.0
    assert by_key["S"]["count"] == 2
    assert by_key["S"]["avg_pollutant"] == 70.0
    assert "角度量" in breakdown["note"]


def test_correlation_rejects_unknown_factor(client, station):
    bad_weather = client.get(
        "/api/weather/correlation?station_id=%d&weather_factor=rainbow" % station.id
    )
    assert bad_weather.status_code == 422
    bad_pollutant = client.get(
        "/api/weather/correlation?station_id=%d&pollutant=XX" % station.id
    )
    assert bad_pollutant.status_code == 422


def test_correlation_export_returns_csv(client, station):
    _seed_paired_series(client, station)
    response = client.get(
        "/api/weather/correlation/export?station_id=%d&pollutant=O3&weather_factor=temperature"
        % station.id
    )
    assert response.status_code == 200
    assert "text/csv" in response.content_type
    data = response.data.decode("utf-8-sig")
    assert "温度(℃)" in data
    assert "O₃(μg/m³)" in data
    assert data.count("\n") == 6  # 表头 + 5 条成对样本


def test_weather_observation_service_accepts_sparse_factors(app, station):
    """同一条观测只填部分要素也应可入库并与浓度配对."""
    with app.app_context():
        result = weather_service.record_observation(
            station_id=station.id,
            measured_at=datetime(2026, 9, 1, 10, 0),
            period="hourly",
            factors={"temperature": 27.5},
        )
        assert result["record"]["humidity"] is None
        assert WeatherRecord.query.count() == 1

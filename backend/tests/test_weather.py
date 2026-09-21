"""气象要素录入、查询、导出与关联分析接口测试."""
from app.domain.weather import sector_of, wind_direction_code, wind_direction_label
from app.models import Measurement, WeatherRecord


def _weather_payload(station_id, measured_at="2026-09-01 10:00", period="hourly", **fields):
    payload = {
        "station_id": station_id,
        "measured_at": measured_at,
        "period": period,
        "data_source": "manual",
        "recorder": "气象员",
        "temperature": 26.5,
        "humidity": 72.0,
        "wind_speed": 2.4,
        "wind_direction": 135.0,
        "pressure": 1006.0,
        "precipitation": 0.0,
    }
    payload.update(fields)
    return payload


def _measurement_entries(station_id, measured_at, value=60.0, period="hourly"):
    return {
        "station_id": station_id,
        "measured_at": measured_at,
        "period": period,
        "entries": [{"pollutant": "PM25", "value": value}],
    }


# ------------------------------------------------------------------ 录入
def test_create_weather_record(client, station):
    response = client.post("/api/weather/entries", json=_weather_payload(station.id))
    assert response.status_code == 201
    body = response.get_json()
    assert body["summary"]["created_count"] == 1
    assert body["summary"]["factor_count"] == 6
    record = body["created"][0]
    assert record["temperature"] == 26.5
    assert record["wind_dir_code"] == "SE"
    assert record["wind_dir_label"] == "东南"
    assert record["station"]["code"] == "TEST-001"


def test_weather_record_partial_factors(client, station):
    payload = _weather_payload(station.id, temperature=30.0, humidity=None)
    for key in ("humidity", "wind_speed", "wind_direction", "pressure", "precipitation"):
        payload[key] = None
    response = client.post("/api/weather/entries", json=payload)
    assert response.status_code == 201
    record = response.get_json()["created"][0]
    assert record["observed_factors"] == ["temperature"]
    assert record["humidity"] is None


def test_weather_record_requires_at_least_one_factor(client, station):
    payload = _weather_payload(station.id)
    for key in ("temperature", "humidity", "wind_speed", "wind_direction",
                "pressure", "precipitation"):
        payload[key] = None
    response = client.post("/api/weather/entries", json=payload)
    assert response.status_code == 422
    assert response.get_json()["error"]["fields"]["entries"] == "empty"


def test_weather_record_range_validation(client, station):
    response = client.post(
        "/api/weather/entries", json=_weather_payload(station.id, humidity=120)
    )
    assert response.status_code == 422
    assert response.get_json()["error"]["fields"]["humidity"] == "out_of_range"

    response = client.post(
        "/api/weather/entries", json=_weather_payload(station.id, wind_direction=400)
    )
    assert response.status_code == 422
    assert response.get_json()["error"]["fields"]["wind_direction"] == "out_of_range"


def test_duplicate_weather_record_conflicts_then_overwrite(client, station):
    payload = _weather_payload(station.id)
    assert client.post("/api/weather/entries", json=payload).status_code == 201
    dup = client.post("/api/weather/entries", json=payload)
    assert dup.status_code == 409

    overwrite = client.post(
        "/api/weather/entries", json=_weather_payload(station.id, temperature=35.0, overwrite=True)
    )
    assert overwrite.status_code == 201
    body = overwrite.get_json()
    assert body["summary"]["updated_count"] == 1
    assert WeatherRecord.query.count() == 1
    assert WeatherRecord.query.one().temperature == 35.0


def test_calm_wind_is_coded_separately(client, station):
    response = client.post(
        "/api/weather/entries",
        json=_weather_payload(station.id, wind_speed=0.1, wind_direction=90.0),
    )
    record = response.get_json()["created"][0]
    assert record["wind_dir_code"] == "C"
    assert record["wind_dir_label"] == "静风"
    assert record["is_calm"] is True


def test_delete_weather_record(client, station):
    created = client.post("/api/weather/entries", json=_weather_payload(station.id)).get_json()
    record_id = created["created"][0]["id"]
    response = client.delete("/api/weather/%s" % record_id)
    assert response.status_code == 200
    assert WeatherRecord.query.count() == 0


def test_station_delete_cascades_weather(client, station):
    client.post("/api/weather/entries", json=_weather_payload(station.id))
    assert WeatherRecord.query.count() == 1
    response = client.delete("/api/stations/%s" % station.id)
    assert response.status_code == 200
    assert WeatherRecord.query.count() == 0


# ------------------------------------------------------------------ 查询
def test_list_and_filter_weather_records(client, station, second_station):
    client.post("/api/weather/entries",
                json=_weather_payload(station.id, measured_at="2026-09-01 10:00", temperature=25.0))
    client.post("/api/weather/entries",
                json=_weather_payload(second_station.id, measured_at="2026-09-02 10:00",
                                      temperature=31.0))

    response = client.get("/api/weather/?station_id=%s" % station.id)
    assert response.status_code == 200
    body = response.get_json()
    assert body["total"] == 1
    assert body["items"][0]["temperature"] == 25.0
    assert body["summary"]["total"] == 1

    by_date = client.get("/api/weather/?date_from=2026-09-02&date_to=2026-09-02")
    assert by_date.get_json()["total"] == 1

    by_factor = client.get("/api/weather/?factor=pressure")
    assert by_factor.get_json()["total"] == 2
    missing = client.get("/api/weather/?factor=precipitation")
    # 两条记录降水量都为 0.0(非空), 仍计入
    assert missing.get_json()["total"] == 2


def test_weather_export_csv(client, station):
    client.post("/api/weather/entries", json=_weather_payload(station.id))
    response = client.get("/api/weather/export")
    assert response.status_code == 200
    text = response.data.decode()
    assert "温度" in text.splitlines()[0]
    assert "东南" in text


def test_context_endpoint(client, station):
    response = client.get("/api/weather/context")
    assert response.status_code == 200
    body = response.get_json()
    codes = [item["code"] for item in body["factors"]]
    assert "temperature" in codes and "wind_direction" in codes
    assert body["stations"][0]["code"] == "TEST-001"


# -------------------------------------------------------------- 关联分析
def _seed_paired_series(client, station_id, points):
    """构造温度与浓度完全正相关、风速与浓度完全负相关的配对序列."""
    for index, (temp, wind, concentration) in enumerate(points):
        ts = "2026-09-01 %02d:00" % index
        client.post(
            "/api/weather/entries",
            json=_weather_payload(station_id, measured_at=ts,
                                  temperature=temp, wind_speed=wind,
                                  humidity=60.0 + index),
        )
        client.post(
            "/api/measurements/entries",
            json=_measurement_entries(station_id, ts, value=concentration),
        )


def test_correlation_numeric_factors(client, station):
    # 温度升 -> 浓度升; 风速与温度反向因此与浓度负相关
    points = [(20.0, 5.0, 10.0), (22.0, 4.0, 20.0), (24.0, 3.0, 30.0),
              (26.0, 2.0, 40.0), (28.0, 1.0, 50.0)]
    _seed_paired_series(client, station.id, points)

    response = client.get(
        "/api/weather/correlation?pollutant=PM25&factor=temperature&station_id=%s" % station.id
    )
    assert response.status_code == 200
    body = response.get_json()
    result = body["result"]
    assert result["kind"] == "numeric"
    assert round(result["pearson_r"], 3) == 1.0
    assert result["direction"] == "正相关"
    assert result["strength"] == "极强相关"
    assert result["sample_count"] == 5
    assert body["sample_total"] == 5
    assert len(body["series"]) == 5
    assert body["series"][0]["pollutant_value"] == 10.0

    wind = client.get(
        "/api/weather/correlation?pollutant=PM25&factor=wind_speed&station_id=%s" % station.id
    ).get_json()["result"]
    assert round(wind["pearson_r"], 3) == -1.0
    assert wind["direction"] == "负相关"


def test_correlation_wind_direction_sectors(client, station):
    pairs = [(0.0, 80.0), (350.0, 70.0), (90.0, 20.0), (95.0, 25.0)]
    for index, (angle, concentration) in enumerate(pairs):
        ts = "2026-09-01 %02d:00" % (index + 1)
        client.post(
            "/api/weather/entries",
            json=_weather_payload(station.id, measured_at=ts, wind_direction=angle, wind_speed=3.0),
        )
        client.post(
            "/api/measurements/entries",
            json=_measurement_entries(station.id, ts, value=concentration),
        )

    body = client.get(
        "/api/weather/correlation?pollutant=PM25&factor=wind_direction&station_id=%s" % station.id
    ).get_json()
    result = body["result"]
    assert result["kind"] == "direction"
    sectors = {item["code"]: item for item in result["sectors"]}
    assert sectors["N"]["count"] == 2  # 0° 与 350° 都归入北方位
    assert sectors["N"]["avg_concentration"] == 75.0
    assert sectors["E"]["count"] == 2
    assert result["prevailing_sector"] == "N"
    assert result["overall_avg_concentration"] == 48.75


def test_correlation_only_uses_same_timestamp_pairs(client, station):
    # 气象时刻与浓度时刻错开, 不应产生配对
    client.post(
        "/api/weather/entries",
        json=_weather_payload(station.id, measured_at="2026-09-01 10:00", temperature=20.0),
    )
    client.post(
        "/api/measurements/entries",
        json=_measurement_entries(station.id, "2026-09-01 11:00", value=50.0),
    )
    body = client.get(
        "/api/weather/correlation?pollutant=PM25&factor=temperature&station_id=%s" % station.id
    ).get_json()
    assert body["sample_total"] == 0
    assert body["result"]["pearson_r"] is None
    assert body["result"]["enough_samples"] is False
    assert body["series"] == []


def test_correlation_respects_date_range(client, station):
    points = [(20.0, 3.0, 10.0), (30.0, 1.0, 50.0), (25.0, 2.0, 30.0), (28.0, 1.5, 45.0)]
    _seed_paired_series(client, station.id, points)
    all_body = client.get(
        "/api/weather/correlation?pollutant=PM25&factor=temperature"
    ).get_json()
    assert all_body["sample_total"] == 4

    ranged = client.get(
        "/api/weather/correlation?pollutant=PM25&factor=temperature"
        "&date_from=2026-09-01&date_to=2026-09-01"
    ).get_json()
    assert ranged["sample_total"] == 4

    empty = client.get(
        "/api/weather/correlation?pollutant=PM25&factor=temperature&date_from=2026-10-01"
    ).get_json()
    assert empty["sample_total"] == 0


def test_correlation_rejects_bad_arguments(client, station):
    assert client.get("/api/weather/correlation?pollutant=XX").status_code == 422
    assert client.get("/api/weather/correlation?factor=rainbow").status_code == 422
    assert client.get("/api/weather/correlation?period=weekly").status_code == 422


def test_correlation_export_pairs(client, station):
    points = [(20.0, 3.0, 10.0), (30.0, 1.0, 50.0), (25.0, 2.0, 30.0)]
    _seed_paired_series(client, station.id, points)
    response = client.get("/api/weather/correlation/export?pollutant=PM25&factor=temperature")
    assert response.status_code == 200
    lines = response.data.decode().splitlines()
    assert len(lines) == 4  # 表头 + 3 条配对
    assert "PM2.5浓度" in lines[0]


def test_only_matching_period_is_paired(client, station):
    client.post(
        "/api/weather/entries",
        json=_weather_payload(station.id, measured_at="2026-09-01 00:00", period="daily",
                              temperature=20.0),
    )
    client.post(
        "/api/measurements/entries",
        json=_measurement_entries(station.id, "2026-09-01 00:00", value=30.0, period="daily"),
    )
    hourly = client.get(
        "/api/weather/correlation?pollutant=PM25&factor=temperature&period=hourly"
    ).get_json()
    daily = client.get(
        "/api/weather/correlation?pollutant=PM25&factor=temperature&period=daily"
    ).get_json()
    assert hourly["sample_total"] == 0
    assert daily["sample_total"] == 1


# -------------------------------------------------------------- 领域规则
def test_wind_direction_coding_rules():
    assert wind_direction_code(0.0) == "N"
    assert wind_direction_code(359.0) == "N"
    assert wind_direction_code(90.0) == "E"
    assert wind_direction_code(180.0) == "S"
    assert wind_direction_code(270.0) == "W"
    assert wind_direction_code(30.0, wind_speed=3.0) == "NNE"
    assert wind_direction_code(90.0, wind_speed=0.1) == "C"
    assert wind_direction_label("C") == "静风"
    assert sector_of(350.0) == "N"
    assert sector_of(100.0) == "E"


def test_unpaired_measurement_does_not_block_weather(client, station):
    # 只有气象记录、没有浓度记录时, 列表与统计仍正常
    client.post("/api/weather/entries", json=_weather_payload(station.id))
    body = client.get("/api/weather/summary").get_json()
    assert body["total"] == 1
    assert body["factor_coverage"]["temperature"] == 1
    assert Measurement.query.count() == 0

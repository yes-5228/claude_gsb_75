"""演示数据生成与启动引导."""
import math
import random
from datetime import date, datetime, timedelta

from .extensions import db
from .models import Exceedance, Measurement, Station

DEMO_STATIONS = [
    {
        "code": "SZ-AQ-001", "name": "市民中心站", "area": "福田区",
        "address": "福田区福中三路市民中心广场", "station_type": "ambient",
        "status": "active", "longitude": 114.0579, "latitude": 22.5410,
        "installed_at": date(2019, 5, 12), "remark": "城市环境评价点",
    },
    {
        "code": "SZ-AQ-002", "name": "华侨城站", "area": "南山区",
        "address": "南山区华侨城生态广场", "station_type": "ambient",
        "status": "active", "longitude": 113.9711, "latitude": 22.5356,
        "installed_at": date(2020, 3, 1), "remark": "城市环境评价点",
    },
    {
        "code": "SZ-AQ-003", "name": "罗湖口岸站", "area": "罗湖区",
        "address": "罗湖区火车站东广场", "station_type": "traffic",
        "status": "active", "longitude": 114.1276, "latitude": 22.5329,
        "installed_at": date(2018, 11, 20), "remark": "道路交通监测点, 早晚高峰浓度偏高",
    },
    {
        "code": "SZ-AQ-004", "name": "宝安中心站", "area": "宝安区",
        "address": "宝安区中心区宝安大道", "station_type": "ambient",
        "status": "active", "longitude": 113.8830, "latitude": 22.5551,
        "installed_at": date(2021, 6, 18), "remark": None,
    },
    {
        "code": "SZ-AQ-005", "name": "龙岗工业园站", "area": "龙岗区",
        "address": "龙岗区宝龙工业区龙岗大道", "station_type": "industrial",
        "status": "active", "longitude": 114.2465, "latitude": 22.7204,
        "installed_at": date(2019, 9, 8), "remark": "周边为工业排放源, 需重点关注 SO₂",
    },
    {
        "code": "SZ-AQ-006", "name": "梧桐山背景站", "area": "罗湖区",
        "address": "罗湖区梧桐山风景区", "station_type": "background",
        "status": "active", "longitude": 114.1837, "latitude": 22.5862,
        "installed_at": date(2017, 4, 2), "remark": "区域背景点, 用于对照评价",
    },
    {
        "code": "SZ-AQ-007", "name": "大鹏生态站", "area": "大鹏新区",
        "address": "大鹏新区葵涌街道", "station_type": "rural",
        "status": "maintenance", "longitude": 114.4798, "latitude": 22.5964,
        "installed_at": date(2022, 8, 15), "remark": "设备检修中, 计划本周恢复",
    },
    {
        "code": "SZ-AQ-008", "name": "前海自贸区站", "area": "南山区",
        "address": "南山区前海湾保税港区", "station_type": "ambient",
        "status": "offline", "longitude": 113.8980, "latitude": 22.5253,
        "installed_at": date(2023, 1, 10), "remark": "站点搬迁停用",
    },
]

POLLUTANT_BASE = {"PM25": 45.0, "PM10": 80.0, "SO2": 30.0, "NO2": 45.0, "CO": 1.5, "O3": 120.0}
HOURLY_FACTOR = {"PM25": 1.0, "PM10": 1.05, "SO2": 0.8, "NO2": 1.1, "CO": 0.9, "O3": 1.3}
STATION_FACTOR = {
    "ambient": 1.0, "traffic": 1.2, "industrial": 1.35, "background": 0.55, "rural": 0.75,
}
HOURLY_POINTS = (2, 8, 14, 20)
RECORDERS = ("李静", "王敏", "陈志强", "赵宇", "孙倩")

# ---- 气象要素模拟参数: 刻意构造可被关联分析识别的浓度-气象关系 ----
WIND_DIR_PICKS = (0, 22.5, 45, 67.5, 90, 135, 180, 225, 270, 315, 337.5)


def _weather_snapshot(period, day, hour, station_type, rng):
    """生成某时刻的一组气象要素, 带日变化与少量噪声."""
    seasonal = 8.0 * math.sin((day.timetuple().tm_yday / 365.0) * 2 * math.pi - math.pi / 2)
    if period == "daily":
        diurnal = 0.0
        wind_base = 2.6
    else:
        diurnal = 4.0 * math.sin(math.pi * (hour - 5) / 12.0)  # 午后最高
        wind_base = 2.0 + (2.2 if hour in (14, 20) else 0.0) + (-0.8 if hour == 2 else 0.0)

    temperature = round(24.0 + seasonal + diurnal + rng.uniform(-1.2, 1.2), 1)
    humidity = round(
        max(25.0, min(98.0, 82.0 - 1.6 * diurnal + rng.uniform(-7.0, 7.0))), 1
    )
    industrial_calm = 0.6 if station_type == "industrial" else 0.0
    wind_speed = round(
        max(0.0, wind_base + industrial_calm * -1.0 + rng.uniform(-0.9, 1.4)), 1
    )
    wind_direction = round(rng.choice(WIND_DIR_PICKS) + rng.uniform(-8.0, 8.0), 1) % 360.0
    pressure = round(1008.0 - 0.25 * (temperature - 24.0) + rng.uniform(-3.0, 3.0), 1)
    precipitation = round(max(0.0, rng.gauss(0.0, 2.2)), 1) if rng.random() < 0.22 else 0.0
    return {
        "temperature": temperature,
        "humidity": humidity,
        "wind_speed": wind_speed,
        "wind_direction": wind_direction,
        "pressure": pressure,
        "precipitation": precipitation,
    }


def _weather_multiplier(pollutant, weather):
    """让部分污染物浓度随气象要素系统性变化, 使关联结果可被直观验证."""
    factor = 1.0
    if pollutant in ("PM25", "PM10"):
        # 高湿利于颗粒物吸湿增长, 大风利于扩散
        factor *= 1.0 + (weather["humidity"] - 70.0) * 0.022
        factor *= 1.0 + (2.5 - weather["wind_speed"]) * 0.14
        if weather["precipitation"] > 0:
            factor *= 0.7  # 降水湿清除
    elif pollutant == "O3":
        factor *= 1.0 + (weather["temperature"] - 24.0) * 0.05  # 高温光化学增强
    elif pollutant == "SO2":
        factor *= 1.0 + (2.5 - weather["wind_speed"]) * 0.12
    return max(0.35, factor)


def _value(pollutant, period, station_type, rng, weather=None):
    base = POLLUTANT_BASE[pollutant] * STATION_FACTOR.get(station_type, 1.0)
    if period == "hourly":
        base *= HOURLY_FACTOR[pollutant]
    if weather is not None:
        base *= _weather_multiplier(pollutant, weather)
    value = base * rng.uniform(0.72, 1.22)
    if rng.random() < 0.12:  # 少量明显超标样本, 便于演示超标标注
        value *= rng.uniform(1.8, 2.6)
    return round(value, 2 if pollutant == "CO" else 1)


def seed_demo_data(days=5, rng=None, recorder_pool=RECORDERS):
    """Generate demo stations, monitoring records and paired weather observations."""
    from .services import measurement_service, weather_service

    rng = rng or random.Random(20260914)
    created_stations = []
    for item in DEMO_STATIONS:
        station = Station(**item)
        db.session.add(station)
        created_stations.append(station)
    db.session.commit()

    today = date.today()
    totals = {
        "stations": len(created_stations), "measurements": 0,
        "exceedances": 0, "weather": 0,
    }
    for station in created_stations:
        for offset in range(days):
            day = today - timedelta(days=offset)

            daily_weather = _weather_snapshot("daily", day, 0, station.station_type, rng)
            daily_entries = [
                {"pollutant": code,
                 "value": _value(code, "daily", station.station_type, rng, daily_weather)}
                for code in POLLUTANT_BASE
            ]
            result = measurement_service.record_entries(
                station_id=station.id,
                measured_at=datetime(day.year, day.month, day.day, 0, 0),
                period="daily",
                entries=daily_entries,
                data_source="device",
                recorder=rng.choice(recorder_pool),
                remark="日均值自动汇总",
            )
            totals["measurements"] += result["summary"]["created_count"]
            totals["exceedances"] += result["summary"]["exceeded_count"]
            weather_service.record_observation(
                station_id=station.id,
                measured_at=datetime(day.year, day.month, day.day, 0, 0),
                period="daily",
                values=daily_weather,
                data_source="device",
                recorder=rng.choice(recorder_pool),
                remark="日均值自动汇总",
            )
            totals["weather"] += 1

            for hour in HOURLY_POINTS:
                hourly_weather = _weather_snapshot(
                    "hourly", day, hour, station.station_type, rng
                )
                hourly_entries = [
                    {"pollutant": code,
                     "value": _value(code, "hourly", station.station_type, rng, hourly_weather)}
                    for code in HOURLY_FACTOR
                ]
                result = measurement_service.record_entries(
                    station_id=station.id,
                    measured_at=datetime(day.year, day.month, day.day, hour, 0),
                    period="hourly",
                    entries=hourly_entries,
                    data_source="manual",
                    recorder=rng.choice(recorder_pool),
                )
                totals["measurements"] += result["summary"]["created_count"]
                totals["exceedances"] += result["summary"]["exceeded_count"]
                weather_service.record_observation(
                    station_id=station.id,
                    measured_at=datetime(day.year, day.month, day.day, hour, 0),
                    period="hourly",
                    values=hourly_weather,
                    data_source="manual",
                    recorder=rng.choice(recorder_pool),
                )
                totals["weather"] += 1

    # 标注一部分超标记录, 让工作台同时存在待办与已处理记录
    from .services import exceedance_service

    exceedances = Exceedance.query.order_by(Exceedance.id.asc()).all()
    annotated = 0
    for index, record in enumerate(exceedances):
        if index % 3 == 0:
            continue
        if index % 3 == 1:
            exceedance_service.annotate(
                record, status="confirmed", note="数据经复核属实, 已通知运维排查周边排放源",
                annotator=rng.choice(recorder_pool),
            )
        else:
            exceedance_service.annotate(
                record, status="ignored", note="仪器校准期间异常值, 已在原始数据中标记无效",
                annotator=rng.choice(recorder_pool),
            )
        annotated += 1
    totals["annotated"] = annotated
    return totals


def reset_database():
    db.drop_all()
    db.create_all()


def ensure_bootstrap(app):
    """Create tables / seed demo data at startup when enabled by config."""
    auto_init = app.config.get("AUTO_INIT_DB")
    auto_seed = app.config.get("AUTO_SEED")
    if not auto_init and not auto_seed:
        return
    with app.app_context():
        try:
            if auto_init:
                db.create_all()
            if auto_seed and db.session.query(Station.id).first() is None:
                app.logger.info("seeding demo data ...")
                seed_demo_data()
        except Exception as exc:  # pragma: no cover - depends on external database
            app.logger.warning("bootstrap skipped: %s", exc)

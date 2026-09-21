"""演示数据生成与启动引导."""
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

# 深圳近海气候的各月平均气温 (℃), 用于生成有季节规律的气象演示数据
MONTHLY_TEMP = {1: 15, 2: 16, 3: 19, 4: 23, 5: 26, 6: 28, 7: 29, 8: 29,
                9: 28, 10: 25, 11: 21, 12: 17}
# 各整点相对日均温的偏差 (昼夜节律)
HOUR_TEMP_DELTA = {2: -3.0, 8: -1.0, 14: 4.0, 20: 1.0}
# 各整点相对日均湿的偏差 (凌晨高、午后低, 与风解耦)
HOUR_HUMIDITY_DELTA = {2: 8.0, 8: 4.0, 14: -10.0, 20: 2.0}


def _hourly_weather(day, hour, rng):
    """生成一次整点气象观测, 各要素取值符合常识范围."""
    temp_base = MONTHLY_TEMP.get(day.month, 20) + HOUR_TEMP_DELTA[hour]
    temperature = round(temp_base + rng.uniform(-2.0, 2.0), 1)
    # 湿度围绕 74% 按昼夜节律波动, 与风速/降水独立
    humidity_base = 74.0 + HOUR_HUMIDITY_DELTA[hour]
    humidity = round(min(98.0, max(28.0, humidity_base + rng.uniform(-9, 9))), 0)
    wind_speed = round(max(0.1, 2.6 + (1.0 if hour == 14 else 0.0) + rng.uniform(-1.6, 2.6)), 1)
    # 夏半年主导偏南风 (120°~220°), 少量其它风向
    if rng.random() < 0.78:
        wind_direction = round(rng.uniform(120, 220), 0)
    else:
        wind_direction = round(rng.choice((30, 60, 250, 290, 330, 10)) + rng.uniform(-15, 15), 0) % 360
    pressure = round(1008 - (temperature - 24) * 0.6 + rng.uniform(-2.0, 2.0), 1)
    precipitation = round(rng.uniform(1.0, 22.0), 1) if rng.random() < 0.16 else 0.0
    return {
        "temperature": temperature,
        "humidity": humidity,
        "wind_speed": wind_speed,
        "wind_direction": wind_direction,
        "pressure": pressure,
        "precipitation": precipitation,
    }


def _daily_weather(hourly_obs):
    """由当日各整点观测汇总出日均气象 (风向取下午主导方位)."""
    def avg(field):
        return round(sum(item[field] for item in hourly_obs) / len(hourly_obs), 1)

    return {
        "temperature": avg("temperature"),
        "humidity": round(avg("humidity")),
        "wind_speed": avg("wind_speed"),
        "wind_direction": hourly_obs[-1]["wind_direction"],
        "pressure": avg("pressure"),
        "precipitation": round(sum(item["precipitation"] for item in hourly_obs), 1),
    }


def _weather_modifier(pollutant, weather):
    """让浓度与同期气象要素形成可辨识的统计关联 (扩散/沉降/光化学规律).

    各污染物只受 1~2 个主导要素影响, 避免多因子互相稀释相关信号。
    """
    if not weather:
        return 1.0
    rain = 0.55 if weather["precipitation"] > 5 else 1.0       # 降水冲刷
    if pollutant in {"PM25", "PM10"}:
        wind = 1.0 - 0.14 * (weather["wind_speed"] - 2.8)
        humidity = 1.0 + 0.006 * (weather["humidity"] - 72.0)  # 吸湿增长, 弱贡献
        return max(0.3, wind * humidity * rain)
    if pollutant in {"SO2", "NO2", "CO"}:
        wind = 1.0 - 0.15 * (weather["wind_speed"] - 2.8)       # 风速越大扩散越好
        return max(0.3, wind * rain)
    if pollutant == "O3":
        temp = 1.0 + 0.07 * (weather["temperature"] - 26.0)     # 高温强光化学生成
        humidity_suppress = 1.3 - 0.004 * weather["humidity"]  # 高湿抑制光化学
        return max(0.35, temp * humidity_suppress)
    return 1.0


def _value(pollutant, period, station_type, rng, weather=None):
    base = POLLUTANT_BASE[pollutant] * STATION_FACTOR.get(station_type, 1.0)
    if period == "hourly":
        base *= HOURLY_FACTOR[pollutant]
    value = base * _weather_modifier(pollutant, weather) * rng.uniform(0.9, 1.1)
    if rng.random() < 0.04:  # 少量明显超标样本, 便于演示超标标注
        value *= rng.uniform(1.8, 2.3)
    return round(value, 2 if pollutant == "CO" else 1)


def seed_demo_data(days=5, rng=None, recorder_pool=RECORDERS):
    """Generate demo stations and monitoring records through the normal service path."""
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
        "stations": len(created_stations), "measurements": 0, "exceedances": 0,
        "weather": 0,
    }
    for station in created_stations:
        for offset in range(days):
            day = today - timedelta(days=offset)
            # 先生成当日各整点气象观测, 浓度取值再与同期气象联动
            hourly_weather = {}
            for hour in HOURLY_POINTS:
                observed_at = datetime(day.year, day.month, day.day, hour, 0)
                factors = _hourly_weather(day, hour, rng)
                weather_result = weather_service.record_observation(
                    station_id=station.id,
                    measured_at=observed_at,
                    period="hourly",
                    factors=factors,
                    data_source="device",
                    recorder=rng.choice(recorder_pool),
                )
                hourly_weather[hour] = factors
                totals["weather"] += 1

            daily_weather = _daily_weather(list(hourly_weather.values()))
            weather_service.record_observation(
                station_id=station.id,
                measured_at=datetime(day.year, day.month, day.day, 0, 0),
                period="daily",
                factors=daily_weather,
                data_source="device",
                recorder=rng.choice(recorder_pool),
                remark="日均气象自动汇总",
            )
            totals["weather"] += 1

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

            for hour in HOURLY_POINTS:
                hourly_entries = [
                    {"pollutant": code,
                     "value": _value(code, "hourly", station.station_type, rng,
                                     hourly_weather[hour])}
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

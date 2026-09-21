"""气象观测记录.

一条记录对应“监测点 + 观测时刻 + 数据周期”的一组气象要素快照
(温度、湿度、风速、风向、气压、降水量), 与 Measurement 按
(station_id, period, measured_at) 对齐, 便于同期对照与关联分析。
"""
from ..domain.constants import DATA_SOURCE_LABELS, PERIOD_LABELS, label_of
from ..domain.weather import (
    MET_FACTORS,
    WIND_DIRECTION_CODE,
    wind_direction_code,
    wind_direction_label,
)
from ..extensions import db
from .base import TimestampMixin, iso

# 模型列名 -> 气象要素编码
NUMERIC_COLUMNS = ("temperature", "humidity", "wind_speed", "pressure", "precipitation")


class WeatherRecord(TimestampMixin, db.Model):
    __tablename__ = "weather_records"
    __table_args__ = (
        db.UniqueConstraint(
            "station_id", "period", "measured_at",
            name="uq_weather_point_time",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    station_id = db.Column(
        db.Integer, db.ForeignKey("stations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    period = db.Column(db.String(16), nullable=False, default="hourly")
    measured_at = db.Column(db.DateTime, nullable=False, index=True)
    temperature = db.Column(db.Float)
    humidity = db.Column(db.Float)
    wind_speed = db.Column(db.Float)
    wind_direction = db.Column(db.Float)
    pressure = db.Column(db.Float)
    precipitation = db.Column(db.Float)
    data_source = db.Column(db.String(16), nullable=False, default="manual")
    recorder = db.Column(db.String(64))
    remark = db.Column(db.Text)

    station = db.relationship("Station", back_populates="weather_records")

    @property
    def wind_dir_code(self):
        return wind_direction_code(self.wind_direction, self.wind_speed)

    @property
    def wind_dir_label(self):
        return wind_direction_label(self.wind_dir_code)

    @property
    def is_calm(self):
        return self.wind_direction is not None and self.wind_dir_code == "C"

    def observed_factors(self):
        """实际填写了观测值的要素编码列表."""
        factors = [code for code in NUMERIC_COLUMNS if getattr(self, code) is not None]
        if self.wind_direction is not None:
            factors.append(WIND_DIRECTION_CODE)
        return factors

    def to_dict(self, include_station=False):
        payload = {
            "id": self.id,
            "station_id": self.station_id,
            "period": self.period,
            "period_label": label_of(PERIOD_LABELS, self.period),
            "measured_at": iso(self.measured_at),
            "temperature": self.temperature,
            "humidity": self.humidity,
            "wind_speed": self.wind_speed,
            "wind_direction": self.wind_direction,
            "wind_dir_code": self.wind_dir_code,
            "wind_dir_label": self.wind_dir_label,
            "is_calm": self.is_calm,
            "pressure": self.pressure,
            "precipitation": self.precipitation,
            "observed_factors": self.observed_factors(),
            "units": {code: meta["unit"] for code, meta in MET_FACTORS.items()},
            "data_source": self.data_source,
            "data_source_label": label_of(DATA_SOURCE_LABELS, self.data_source),
            "recorder": self.recorder,
            "remark": self.remark,
            "created_at": iso(self.created_at),
            "updated_at": iso(self.updated_at),
        }
        if include_station and self.station:
            payload["station"] = {
                "id": self.station.id,
                "code": self.station.code,
                "name": self.station.name,
                "area": self.station.area,
            }
        return payload

    def __repr__(self):
        return "<WeatherRecord %s %s>" % (self.station_id, self.measured_at)

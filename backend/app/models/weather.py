"""气象要素观测记录 (与同期浓度逐时刻对照)."""
from ..domain.constants import DATA_SOURCE_LABELS, PERIOD_LABELS, label_of
from ..extensions import db
from .base import TimestampMixin, iso


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
    temperature = db.Column(db.Float)        # 温度 ℃
    humidity = db.Column(db.Float)           # 相对湿度 %
    wind_speed = db.Column(db.Float)         # 风速 m/s
    wind_direction = db.Column(db.Float)     # 风向 (正北顺时针角度 °)
    pressure = db.Column(db.Float)           # 大气压 hPa
    precipitation = db.Column(db.Float)      # 降水量 mm
    measured_at = db.Column(db.DateTime, nullable=False, index=True)
    data_source = db.Column(db.String(16), nullable=False, default="manual")
    recorder = db.Column(db.String(64))
    remark = db.Column(db.Text)

    station = db.relationship("Station", back_populates="weather_records")

    def factor_value(self, factor):
        return getattr(self, factor, None)

    def to_dict(self, include_station=False):
        payload = {
            "id": self.id,
            "station_id": self.station_id,
            "period": self.period,
            "period_label": label_of(PERIOD_LABELS, self.period),
            "temperature": self.temperature,
            "humidity": self.humidity,
            "wind_speed": self.wind_speed,
            "wind_direction": self.wind_direction,
            "pressure": self.pressure,
            "precipitation": self.precipitation,
            "measured_at": iso(self.measured_at),
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

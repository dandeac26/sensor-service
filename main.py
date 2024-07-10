from fastapi import FastAPI, Depends
from sqlalchemy import create_engine, Column, Integer, String, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
import paho.mqtt.client as mqtt
import json
from fastapi import HTTPException
from pydantic import BaseModel
from typing import List
from contextlib import contextmanager
from datetime import datetime, timedelta
from dateutil.parser import parse
import logging
import httpx
import os

logging.basicConfig(level=logging.INFO)

TEMPERATURE_THRESHOLD = float(os.getenv("TEMPERATURE_THRESHOLD"))
HUMIDITY_THRESHOLD = float(os.getenv("HUMIDITY_THRESHOLD"))

DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_PORT = os.getenv("DB_PORT")

WEB_SOCKET_SERVICE_URL = os.getenv("WS_HOST")
WEB_SOCKET_SERVICE_PORT = os.getenv("WS_PORT")

MQTT_SERVER = os.getenv("MQTT_HOST")

SQLALCHEMY_DATABASE_URL = "postgresql://" + DB_USER + ":" + DB_PASSWORD + "@" + DB_HOST + ":" + DB_PORT + "/sensor_db"

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, index=True)
    sensorId = Column(String)
    timestamp = Column(String)
    temperature = Column(Float)
    humidity = Column(Float)


Base.metadata.create_all(bind=engine)

app = FastAPI()


@app.post("/sensor-data/")
def store_sensor_data(sensor_id: str, timestamp: str, temperature: float, humidity: float):
    with get_db() as db:
        existing_data = db.query(SensorReading).filter(SensorReading.sensorId == sensor_id,
                                                       SensorReading.timestamp == timestamp,
                                                       SensorReading.temperature == temperature,
                                                       SensorReading.humidity == humidity).first()
        if existing_data is None:
            db_sensor_reading = SensorReading(sensorId=sensor_id, timestamp=timestamp, temperature=temperature,
                                              humidity=humidity)
            db.add(db_sensor_reading)
            db.commit()
            db.refresh(db_sensor_reading)
            return {"message": "Sensor data stored successfully"}
        else:
            return {"message": "Data already exists"}


old_timestamp = datetime.now() - timedelta(minutes=1)


def on_message(client, userdata, msg):
    global old_timestamp

    temperature_threshold = TEMPERATURE_THRESHOLD
    humidity_threshold = HUMIDITY_THRESHOLD

    data = json.loads(msg.payload.decode())

    sensor_id = data["sensorId"]
    temperature = float(data["temperature"])
    humidity = float(data["humidity"])
    timestamp_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')

    if (temperature >= temperature_threshold or humidity >= humidity_threshold) and (
            timestamp - old_timestamp >= timedelta(minutes=1)):

        old_timestamp = timestamp

        payload = {
            "sensorId": sensor_id,
            "temperature": temperature,
            "humidity": humidity,
            "timestamp": timestamp_str
        }

        response = httpx.post(
            "http://" + WEB_SOCKET_SERVICE_URL + ":" + WEB_SOCKET_SERVICE_PORT + "/notification/sensor-alert",
            json=payload)

        if response.status_code == 200:
            print("Alert sent successfully")
        else:
            old_timestamp = datetime.now() - timedelta(minutes=1)
            print(f"Failed to send alert: {response.content}")

    with get_db() as db:
        existing_data = db.query(SensorReading).filter(SensorReading.sensorId == sensor_id,
                                                       SensorReading.timestamp == timestamp_str,
                                                       SensorReading.temperature == temperature,
                                                       SensorReading.humidity == humidity).first()
        if existing_data is None:
            db_sensor_reading = SensorReading(sensorId=sensor_id, timestamp=timestamp_str, temperature=temperature,
                                              humidity=humidity)
            db.add(db_sensor_reading)
            db.commit()
            db.refresh(db_sensor_reading)
            print(f"Stored sensor data: {msg.payload.decode()}")
        else:
            print(f"Data already exists: {msg.payload.decode()}")


@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class SensorReadingBase(BaseModel):
    sensorId: str
    timestamp: str
    temperature: float
    humidity: float


@app.get("/sensor-data", response_model=List[SensorReadingBase])
def read_sensor_data():
    with get_db() as db:
        sensor_data = db.query(SensorReading).all()
        if sensor_data is None:
            raise HTTPException(status_code=404, detail="No sensor data found")
        return [SensorReadingBase(**item.__dict__) for item in sensor_data]


@app.get("/sensor-data/last-hour", response_model=List[SensorReadingBase])
def read_sensor_data_last_hour():
    with get_db() as db:
        one_hour_ago = datetime.now() - timedelta(hours=1)
        sensor_data = db.query(SensorReading).all()
        sensor_data_last_hour = [data for data in sensor_data if parse(data.timestamp) >= one_hour_ago]
        if not sensor_data_last_hour:
            raise HTTPException(status_code=404, detail="No sensor data found in the last hour")
        return [SensorReadingBase(**item.__dict__) for item in sensor_data_last_hour]


@app.get("/sensor-data/last-day", response_model=List[SensorReadingBase])
def read_sensor_data_last_day():
    one_day_ago = datetime.now() - timedelta(days=1)
    with get_db() as db:
        sensor_data = db.query(SensorReading).all()
        sensor_data_last_day = [data for data in sensor_data if parse(data.timestamp) >= one_day_ago]
        if sensor_data_last_day is None:
            raise HTTPException(status_code=404, detail="No sensor data found in the last day")
        return [SensorReadingBase(**item.__dict__) for item in sensor_data_last_day]


@app.get("/sensor-data/{sensor_id}", response_model=List[SensorReadingBase])
def read_sensor_data_by_id(sensor_id: str):
    with get_db() as db:
        sensor_data = db.query(SensorReading).filter(SensorReading.sensorId == sensor_id).all()
        if sensor_data is None:
            raise HTTPException(status_code=404, detail="No sensor data found for this sensorId")
        return [SensorReadingBase(**item.__dict__) for item in sensor_data]


@app.get("/sensor-data/{sensor_id}/last-day", response_model=List[SensorReadingBase])
def read_sensor_data_of_last_day_by_id(sensor_id: str):
    one_day_ago = datetime.now() - timedelta(days=1)
    with get_db() as db:
        sensor_data = db.query(SensorReading).filter(SensorReading.sensorId == sensor_id).all()
        sensor_data_last_day = [data for data in sensor_data if parse(data.timestamp) >= one_day_ago]
        if sensor_data_last_day is None:
            raise HTTPException(status_code=404, detail="No sensor data found for this sensorId")
        return [SensorReadingBase(**item.__dict__) for item in sensor_data_last_day]


@app.get("/sensor-data/{sensor_id}/last-hour", response_model=List[SensorReadingBase])
def read_sensor_data_of_last_hour_by_id(sensor_id: str):
    with get_db() as db:
        one_hour_ago = datetime.now() - timedelta(hours=1)
        sensor_data = db.query(SensorReading).filter(SensorReading.sensorId == sensor_id).all()
        sensor_data_last_hour = [data for data in sensor_data if parse(data.timestamp) >= one_hour_ago]
        if sensor_data_last_hour is None:
            raise HTTPException(status_code=404, detail="No sensor data found for this sensorId")
        return [SensorReadingBase(**item.__dict__) for item in sensor_data_last_hour]


client = mqtt.Client()
client.on_message = on_message
client.connect(MQTT_SERVER, 1883, 60)
client.subscribe("sensor/topic")
client.loop_start()

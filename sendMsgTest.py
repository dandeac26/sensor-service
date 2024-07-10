import paho.mqtt.client as mqtt


client = mqtt.Client()

client.connect("localhost", 1883, 60)

client.publish("sensor/topic", "sensor1,23.5,45.2")

client.disconnect()
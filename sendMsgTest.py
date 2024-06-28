import paho.mqtt.client as mqtt

# Create a MQTT client
client = mqtt.Client()

# Connect to the MQTT server
client.connect("localhost", 1883, 60)

# Publish a message to the topic
# The message is a comma-separated string: "sensorId,temperature,humidity"
client.publish("sensor/topic", "sensor1,23.5,45.2")

# Disconnect from the MQTT server
client.disconnect()
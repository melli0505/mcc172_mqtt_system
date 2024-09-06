
import time
from paho.mqtt import client as mqtt
from threading import Lock
import RPi.GPIO as GPIO

sensor = 22

GPIO.setmode(GPIO.BCM) 
GPIO.setup(sensor,GPIO.IN) 

sample = 1000
count = 0

start = 0
end = 0

broker_address =  "SERVER_ADDRESS"
client = mqtt.Client("motor_rpm")
client.connect(broker_address, 1883)

def get_rpm(c):
	global count, rpm
	count = count + 1

print("Add event listener...")
GPIO.add_event_detect(sensor, GPIO.RISING, callback=get_rpm) 
print("Start!")

try:
	start = time.time()
	while True: 
		end = time.time()
		if end - start >= 60:
			delta = (end - start) / 60
			count = int(count / delta / 2)
			client.publish("motor_rpm", str(count)
			count = 0
			start = end
except KeyboardInterrupt:
	print( "  Quit")
	GPIO.cleanup()

'''Wrapper on Py-SDS011 interface 

The MIT License (MIT)

Copyright (c) 208 Stephen Suffian

'''

from lib.sds011 import SDS011
import time

def mean(values):
    if len(values) > 0:
        return sum(values)/float(len(values))
    else:
        return -1

def init_sensor_and_wait():
    sensor = SDS011()
    sensor.sleep(sleep=False)
    time.sleep(5)
    return sensor

def get_fake_values(sensor):
    #Used to flush out the fake initial values
    sensor.query()
    sensor.query()
    sensor.query()

def get_values(sensor, num_values=5):
    pm25_values = []
    pm10_values = []
    for i in range(0, num_values):
        time.sleep(1)
        value = sensor.query()
        if value is not None:
            pm25_values.append(value[0])
            pm10_values.append(value[1])
        print(value)
    return pm25_values, pm10_values

def close(sensor):
    sensor.sleep()

def run_sensor(num_values=5):
    sensor = init_sensor_and_wait()
    get_fake_values(sensor)
    pm25_values, pm10_values = get_values(sensor, num_values)
    #close(sensor)
    print(' PM2.5: {}, PM10: {}'.format(mean(pm25_values),mean(pm10_values)))
    return mean(pm25_values), mean(pm10_values)

if __name__ == '__main__':
    pm25_values, pm10_values = run_sensor(5)

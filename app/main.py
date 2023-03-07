import time
from machine import Pin, ADC
import network
import urequests
import gc
import micropython
import os
import rp2
from utime import sleep
from machine import I2C
from bme280_int import *
import secrets

SLEEP_INTERVAL_SECONDS = 5
USE_WLAN_HW_SWITCH = True
USE_LOGGING = False
USE_STATIC_IP = False

batteryAdc = machine.ADC(26) 

sda = machine.Pin(0)
scl = machine.Pin(1)
i2c = machine.I2C(0, sda = sda, scl = scl, freq=400000)

ssid = secrets.secrets['ssid']
password = secrets.secrets['password']

rp2.country('PL')

IP = "192.168.2.187"
IP_mask = "255.255.255.0"
IP_gateway = "192.168.2.1"
IP_DNS = "1.1.1.1"

if USE_LOGGING:
    logfile = open('log.txt', 'a')
    os.dupterm(logfile)

led = machine.Pin('LED', machine.Pin.OUT)

STAT_UP = 3
wlan = None

if USE_WLAN_HW_SWITCH:
    wlanSw = machine.Pin(23, Pin.OUT)

def printWlanStatus():
    # 0  Link Down
    # 1  Link Join
    # 2  Link NoIp
    # 3  Link Up
    # -1 Link Fail
    # -2 Link NoNet
    # -3 Link BadAuth
    
    wlanStatus = wlan.status()
    
    if wlanStatus == network.STAT_IDLE:
        print("STAT_IDLE")
    elif wlanStatus == network.STAT_CONNECTING:
        print("STAT_CONNECTING")
    elif wlanStatus == network.STAT_NO_AP_FOUND:
        print("STAT_NO_AP_FOUND")
    elif wlanStatus == network.STAT_CONNECT_FAIL:
        print("STAT_CONNECT_FAIL")
    elif wlanStatus == network.STAT_GOT_IP:
        print("STAT_GOT_IP")
    elif wlanStatus == network.STAT_WRONG_PASSWORD:
        print("STAT_WRONG_PASSWORD")
    else:
        print("Unknown status: " + str(wlanStatus))

def setupWifi():
    try:
        if USE_WLAN_HW_SWITCH:
            global wlanSw
            wlanSw.high()
        
        time.sleep_ms(500)
        
        global wlan
        wlan = network.WLAN(network.STA_IF)
        
        if USE_STATIC_IP:
            wlan.ifconfig((IP, IP_mask, IP_gateway, IP_DNS))
        
        wlan.active(True)
        wlan.config(pm = 0xa11140)
        
        wlan.connect(ssid, password)
        
        wlandelay =  time.ticks_ms() + 5000
        while time.ticks_ms() < wlandelay:
            #printWlanStatus()
            
            if wlan.isconnected():
                if wlan.status() < 0  or wlan.status() >= STAT_UP:
                    break
                
            machine.idle()
        
        return wlan.status() == STAT_UP
    except Exception as e:
      print("EXCEPTION CAPTURED (connect):\n",e)
      machine.reset()

def connectWifi():
    for i in range(3):
        if setupWifi() == False:
            disconnect()
            continue
        else:
            return True
    return False

def disconnect():
    try:
        print('Disconnecting...')
        
        if USE_WLAN_HW_SWITCH:
            global wlanSw
            wlanSw.low()
        
        time.sleep_ms(100)
        
        global wlan
        wlan.disconnect()
        wlan.active(False)
        wlan.deinit()
        wlan = None
        
        time.sleep_ms(100)
        
        print("Disconnected!")
    except Exception as e:
      print("EXCEPTION CAPTURED (disconnect):\n",e)
      
def measureBatteryVoltage():
    batteryVoltage = batteryAdc.read_u16()
    return (batteryVoltage * 3.3 / 65535) * 2
      
def measure_vsys():
    Pin(25, Pin.OUT, value=1)
    Pin(29, Pin.IN, pull=None)
    reading = ADC(3).read_u16() * 9.9 / 2**16
    Pin(25, Pin.OUT, value=0, pull=Pin.PULL_DOWN)
    Pin(29, Pin.ALT, pull=Pin.PULL_DOWN, alt=7)
    return reading

def measureDataAndSend():
    try:
        vs = measure_vsys()
        freeMemory = gc.mem_free()
        allocatedMemory = gc.mem_alloc()
        bme280 = BME280(i2c=i2c)
        bmeData = bme280.read_compensated_data()
        temperature = bmeData[0]
        pressure = bmeData[1]
        humidity = bmeData[2]
        batteryVoltage = measureBatteryVoltage()
        endpoint = secrets.secrets['endpoint']
        r = urequests.get(endpoint + "/?vsys=" + str(vs) + "&mem_free=" + str(freeMemory) + "&mem_allocated=" + str(allocatedMemory) + "&temperature=" + str(temperature) + "&humidity=" + str(humidity) + "&pressure=" + str(pressure) + "&battery=" + str(batteryVoltage))
        r.close()
    except Exception as e:
      print("EXCEPTION CAPTURED (measureVsysAndSend):\n",e)

while True:
    if not connectWifi():
        print('Not connected to WiFi, resetting machine...')
        time.sleep_ms(500)
        machine.reset()
    
    led.value(True)
    time.sleep_ms(250)
    led.value(False)
    
    measureDataAndSend()
    
    time.sleep_ms(750)
    disconnect()
    time.sleep_ms(100)
    
    print('Before deep sleep...')
    
    batteryVoltage = measureBatteryVoltage()
    if batteryVoltage > 4.1 :
        machine.lightsleep(60000)  #60 sec cycle
    elif batteryVoltage > 4.0 :
        machine.lightsleep(120000)  #120 sec cycle
    elif batteryVoltage > 3.6:
        machine.lightsleep(300000) #180 sec cycle
    else:
        machine.lightsleep(600000) #5 min cycle
    
    time.sleep_ms(100)
    
    print('After deep sleep!!!')


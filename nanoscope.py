## Simple view of a single channel at rate 230400
## python3 ./nanoscope.py --input /dev/tty.usbserial-14140 --rate 230400

## Capture a single channel into a file
## python3 ./nanoscope.py --input /dev/tty.usbserial-14140 --rate 230400 --capture output.dat

## Display captured data, and vertically scale to 0.5 height, 1.5 width
## python ./nanoscope.py --input output.dat --scale 0.5 --zoom 1.5

## Display two channels (one on COM7 and one on COM9)
## python ./nanoscope.py --input COM7 --rate 230400 --input2 COM9 --rate2 230400

## Oscillofun:
## Assuming COM7 = Left Channel, COM9 = Right Channel
## python ./nanoscope.py --input COM7 --rate 230400 --invert --offset -100 --input2 COM9 --invert2 --offset2 -220 --rate2 230400 --xy

import pyglet
import math
import serial
import argparse
import time

from pyglet import shapes
from pyglet.gl import *
from pyglet.window import mouse
from pyglet.window import key

parser = argparse.ArgumentParser(description='nanoscope - a simple viewer for streaming serial input data.')
parser.add_argument('--input', required=True, dest='input', type=str, help='Path to input serial data stream')
parser.add_argument('--peak', dest='peak', default=1024, type=int, help='Maximum possible value of input data points')
parser.add_argument('--rate', dest='rate', type=int, help='Baud rate of input serial data stream')
parser.add_argument('--vref', dest='vref', default=5, type=float, help='Voltage value when at input peak')
parser.add_argument('--scale', dest='scale', default=1, type=float, help='Vertical zoom to apply to data view')
parser.add_argument('--zoom', dest='zoom', default=1, type=float, help='Horizontal zoom to apply to data view')
parser.add_argument('--offset', dest='offset', default=0, type=int, help='Offset to apply to data view')
parser.add_argument('--trigger', dest='trigger', default=1, type=float, help='Trigger point (in either volts or raw data value)')
parser.add_argument('--invert', dest='invert', default=False, action='store_true', help='Whether to invert the channel')
parser.add_argument('--capture', dest='capture', type=str, help='Path to capture data stream to')

parser.add_argument('--input2', dest='input2', type=str, help='[2nd channel] Path to input serial data stream')
parser.add_argument('--peak2', dest='peak2', default=1024, type=int, help='[2nd channel] Maximum possible value of input data points')
parser.add_argument('--rate2', dest='rate2', type=int, help='[2nd channel] Baud rate of input serial data stream')
parser.add_argument('--vref2', dest='vref2', default=5, type=float, help='[2nd channel] Voltage value when at input peak')
parser.add_argument('--scale2', dest='scale2', default=1, type=float, help='[2nd channel] Vertical zoom to apply to data view')
parser.add_argument('--zoom2', dest='zoom2', default=1, type=float, help='[2nd channel] Horizontal zoom to apply to data view')
parser.add_argument('--offset2', dest='offset2', default=0, type=int, help='[2nd channel] Offset to apply to data view')
parser.add_argument('--invert2', dest='invert2', default=False, action='store_true', help='[2nd channel] Whether to invert the channel')
parser.add_argument('--capture2', dest='capture2', type=str, help='[2nd channel] Path to capture data stream to')

parser.add_argument('--oneshot', dest='oneshot', default=False, action='store_true', help='Stop capturing once trigger point has hit')
parser.add_argument('--xy', dest='xy', default=False, action='store_true', help='Display input channels in XY mode')

args = parser.parse_args()

channels = [{
    "input": args.input,
    "peak": args.peak,
    "rate": args.rate,
    "vref": args.vref,
    "scale": args.scale,    
    "zoom": args.zoom,
    "offset": args.offset,
    "trigger": args.trigger,
    "invert": args.invert,
    "capture": args.capture,

    "originalTrigger": None,
    "port": None,
    "dataBuffer": [0]*10*10000,
    "dataIndex":  0,
    "triggerIndex": -1,
    "oneShotHome": -1,
    "captureFile": None,
    "sampleTotal": 0
}, {
    "input": args.input2,
    "peak": args.peak2,
    "rate": args.rate2,
    "vref": args.vref2,
    "scale": args.scale2,    
    "zoom": args.zoom2,
    "offset": args.offset2,
    "trigger": -1,
    "invert": args.invert2,
    "capture": args.capture2,

    "originalTrigger": None,
    "port": None,
    "dataBuffer": [0]*10*10000,
    "dataIndex":  0,
    "triggerIndex": -1,
    "oneShotHome": -1,
    "captureFile": None,
    "sampleTotal": 0
}]

for channel in channels:

    ## Adjust trigger if they specified something in volts
    if channel["trigger"] < 10:
        channel["trigger"] = channel["trigger"] / channel["vref"] * channel["peak"]
        channel["originalTrigger"] = channel["trigger"]

    if channel["input"] is not None:      
        if (channel["input"].lower().startswith("/dev") or channel["input"].lower().startswith("com")) and channel["rate"] is None:
            raise Exception("Specify a serial rate for " + channel["input"])
        try:
            channel["port"] = serial.Serial(channel["input"], channel["rate"])

        except Exception as e:
            channel["port"] = None

        if channel["port"] is None:
            dataFile = open(channel["input"], "rb")
            channel["dataBuffer"] = dataFile.read()
            channel["dataIndex"] = 0

    if channel["capture"] is not None:
        channel["captureFile"] = open(channel["capture"], "wb")

def getSamples():

    samples = [getSample(channels[0]), getSample(channels[1])]
    return samples

def getSample(channel):

    if channel["input"] is None:
        return 0

    try:
        ## Read an integer as two bytes, big-endian
        if (channel["port"] is not None) and (channel["triggerIndex"] < 0):

            inputHigh, inputLow = channel["port"].read(2)
            channel["sampleTotal"] = channel["sampleTotal"] + 2

            ## If this data point is out of range, we've had a sync error
            ## so read in another byte.
            while ((inputHigh << 8) | inputLow) > channel["peak"]:
                inputHigh = inputLow
                inputLow = channel["port"].read(1)[0]
                channel["sampleTotal"] = channel["sampleTotal"] + 1

            channel["dataBuffer"][channel["dataIndex"]] = inputHigh
            channel["dataIndex"] = (channel["dataIndex"] + 1) % len(channel["dataBuffer"])
            channel["dataBuffer"][channel["dataIndex"]] = inputLow
            channel["dataIndex"] = (channel["dataIndex"] + 1) % len(channel["dataBuffer"])

        else:
            inputHigh = channel["dataBuffer"][channel["dataIndex"]]
            channel["dataIndex"] = (channel["dataIndex"] + 1) % len(channel["dataBuffer"])
            inputLow = channel["dataBuffer"][channel["dataIndex"]]
            channel["dataIndex"] = (channel["dataIndex"] + 1) % len(channel["dataBuffer"])

            ## If this data point is out of range, we've had a sync error
            ## so read in another byte.
            while ((inputHigh << 8) | inputLow) > channel["peak"]:
                inputHigh = inputLow
                inputLow = channel["dataBuffer"][channel["dataIndex"]]
                channel["dataIndex"] = (channel["dataIndex"] + 1) % len(channel["dataBuffer"])

        inputData = (inputHigh << 8) | (inputLow)

        if channel["captureFile"] is not None:
            channel["captureFile"].write(inputData.to_bytes(2, 'big'))

        if channel["invert"]:
            return channel["peak"] - inputData
        else:
            return inputData

    except Exception as e:
        print(e)
        inputData = 0

    if channel["captureFile"] is not None:
        channel["captureFile"].write(inputData.to_bytes(2, 'big'))


def update(dt):
    pass

oneShot = args.oneshot
xy = args.xy

mousePos = 0, 0
mouseDragStart = 0, 0
currentFrame = 0

window = pyglet.window.Window(resizable=True)
pyglet.clock.schedule_interval(update, 1/30.0)

@window.event
def on_mouse_motion(x, y, dx, dy):
    global mousePos
    mousePos = x, y

@window.event
def on_mouse_press(x, y, buttons, modifiers):
    global mouseDragStart
    mouseDragStart = x, y

@window.event
def on_mouse_drag(x, y, dx, dy, buttons, modifiers):
    global mousePos
    mousePos = x, y

@window.event
def on_mouse_release(x, y, button, modifiers):
    global mouseDragStart
    mouseDragStart = 0, 0

@window.event
def on_key_press(symbol, modifiers):

    ## X
    ## Toggle XY mode
    if symbol == key.X:
        global xy
        xy = not xy

    ## T
    ## Reset triggers
    if symbol == key.T:
        channels[0]["trigger"] = channels[0]["originalTrigger"]
        channels[1]["trigger"] = channels[1]["originalTrigger"]

    ## Ctrl +/-/0
    ## Change the horizontal scale
    if symbol == key.EQUAL and (modifiers & key.MOD_CTRL):
        channels[0]["zoom"] = channels[0]["zoom"] * 1.1
        channels[1]["zoom"] = channels[1]["zoom"] * 1.1

    if symbol == key.MINUS and (modifiers & key.MOD_CTRL):
        channels[0]["zoom"] = channels[0]["zoom"] / 1.1
        channels[1]["zoom"] = channels[1]["zoom"] / 1.1

    if symbol == key._0 and (modifiers & key.MOD_CTRL):
        channels[0]["zoom"] = 1.0
        channels[1]["zoom"] = 1.0

    ## Alt +/-/0
    ## Change the vertical scale
    if symbol == key.EQUAL and (modifiers & key.MOD_ALT):
        channels[0]["scale"] = channels[0]["scale"] * 1.1
        channels[1]["scale"] = channels[1]["scale"] * 1.1

    if symbol == key.MINUS and (modifiers & key.MOD_ALT):
        channels[0]["scale"] = channels[0]["scale"] / 1.1
        channels[1]["scale"] = channels[1]["scale"] / 1.1

    if symbol == key._0 and (modifiers & key.MOD_ALT):
        channels[0]["scale"] = 1.0
        channels[1]["scale"] = 1.0

    ## Left, Right, Home
    ## Scroll the view
    if symbol == key.RIGHT:
        ## Use the current data posision if we don't already have one
        if channels[0]["triggerIndex"] < 0:
            channels[0]["triggerIndex"] = channels[0]["dataIndex"]
            channels[1]["triggerIndex"] = channels[1]["dataIndex"]

        if modifiers & key.MOD_CTRL:
            channels[0]["triggerIndex"] = channels[0]["triggerIndex"] + 400
            channels[1]["triggerIndex"] = channels[1]["triggerIndex"] + 400
        else:
            channels[0]["triggerIndex"] = channels[0]["triggerIndex"] + 20
            channels[1]["triggerIndex"] = channels[1]["triggerIndex"] + 20

        if channels[0]["triggerIndex"] >= len(channels[0]["dataBuffer"]):
            channels[0]["triggerIndex"] = channels[0]["triggerIndex"] - len(channels[0]["dataBuffer"])

        if channels[1]["triggerIndex"] >= len(channels[1]["dataBuffer"]):
            channels[1]["triggerIndex"] = channels[1]["triggerIndex"] - len(channels[1]["dataBuffer"])

    if symbol == key.LEFT:
        ## Use the current data posision if we don't already have one
        if channels[0]["triggerIndex"] < 0:
            channels[0]["triggerIndex"] = channels[0]["dataIndex"]
            channels[1]["triggerIndex"] = channels[1]["dataIndex"]

        if modifiers & key.MOD_CTRL:
            channels[0]["triggerIndex"] = channels[0]["triggerIndex"] - 400
            channels[1]["triggerIndex"] = channels[1]["triggerIndex"] - 400
        else:
            channels[0]["triggerIndex"] = channels[0]["triggerIndex"] - 20
            channels[1]["triggerIndex"] = channels[1]["triggerIndex"] - 20

        if channels[0]["triggerIndex"] < 0:
            channels[0]["triggerIndex"] = len(channels[0]["dataBuffer"]) + channels[0]["triggerIndex"]

        if channels[1]["triggerIndex"] < 0:
            channels[1]["triggerIndex"] = len(channels[1]["dataBuffer"]) + channels[1]["triggerIndex"]

    if symbol == key.HOME:
        if channels[0]["oneShotHome"] > 0:
            channels[0]["triggerIndex"] = channels[0]["oneShotHome"]
        else:
            channels[0]["triggerIndex"] = 0

        if channels[1]["oneShotHome"] > 0:
            channels[1]["triggerIndex"] = channels[1]["oneShotHome"]
        else:
            channels[1]["triggerIndex"] = 0

    ## Escape
    ## Go back to live view
    if symbol == key.ESCAPE:
        channels[0]["triggerIndex"] = -1
        channels[1]["triggerIndex"] = -1
        return pyglet.event.EVENT_HANDLED        

@window.event
def on_draw():
    frameBegin = time.perf_counter()
    batch = pyglet.graphics.Batch()

    ## Figure out how many data points we'll need this frame
    ## For XY mode, assume 400. Given the bandwidth of an Arduino
    ## Nano, More than that starts to drop frame rate.
    if xy:
        iterCount = 300
    else:
        iterCount = int(window.width / channels[0]["zoom"])

    ## Wait to buffer enough samples to satisfy the entire frame, and then
    ## toss the rest. This keeps us reading the most current data, avoiding
    ## latency issues (single channel), and differing data rates (dual channel)
    if channels[0]["port"] is not None:
        while channels[0]["port"].in_waiting < iterCount:
            pass
        waiting0 = channels[0]["port"].in_waiting
        channels[0]["port"].read(waiting0 - iterCount)

    if channels[1]["port"] is not None:
        while channels[1]["port"].in_waiting < iterCount:
            pass
        waiting1 = channels[1]["port"].in_waiting
        channels[1]["port"].read(waiting1 - iterCount)
   
    ## If we are in X-Y mode, disable triggering
    if xy:
        channels[0]["trigger"] = -1
        channels[1]["trigger"] = -1
        label = pyglet.text.Label('X-Y mode on ' + channels[0]["input"] + " and "  + channels[1]["input"],
                                font_size=15,
                                x=window.width / 2,
                                y=window.height - 20,
                                anchor_x='center',
                                anchor_y='center',
                                batch = batch)
    else:
        label = pyglet.text.Label(channels[0]["input"],
                                font_size=15,
                                x=window.width / 2,
                                y=window.height - 20,
                                anchor_x='center',
                                anchor_y='center',
                                batch = batch)
        label.color = (120, 120, 220, 255)

        if channels[1]["input"] is not None:
            label.x = window.width / 3
            label2 = pyglet.text.Label(channels[1]["input"],
                                    font_size=15,
                                    x=2 * (window.width / 3),
                                    y=window.height - 20,
                                    anchor_x='center',
                                    anchor_y='center',
                                    batch = batch)
            label2.color = (120, 220, 120, 255)                                    


    ## If we haven't had a oneshot trigger, process a normal trigger
    if channels[0]["triggerIndex"] < 0:
        if not oneShot:
            lastValue = 10000
            triggerAttempts = 0

            ## Rising trigger - wait for the value to go below trigger threshold
            ## and then wait for the value to rise above the trigger
            while channels[0]["trigger"] > 0 and (triggerAttempts < 10000) and lastValue > channels[0]["trigger"]:
                lastValue = getSamples()[0]
                triggerAttempts = triggerAttempts + 1
            
            while channels[0]["trigger"] > 0 and (triggerAttempts < 10000) and lastValue < channels[0]["trigger"]:
                lastValue = getSamples()[0]
                triggerAttempts = triggerAttempts + 1

            ## Disable the trigger if it timed out
            if triggerAttempts == 10000:
                channels[0]["trigger"] = -1
    else:
        channels[0]["dataIndex"] = channels[0]["triggerIndex"]
        channels[1]["dataIndex"] = channels[1]["triggerIndex"]

    ## Prepare the array that will hold the Pyglet shapes / data points
    elements = [0]*((2 * iterCount) + int((window.height - 80) / 10))
    elementIndex = 0

    ## Add the graph lines
    for i in range(0, window.height - 80, 10):
        if i % 100 == 0:
            elements[elementIndex] = shapes.Line(0, i + 40, window.width, i + 40, color = (200, 200, 200), width = 1, batch = batch)
        else:
            elements[elementIndex] = shapes.Line(0, i + 40, window.width, i + 40, color = (100, 100, 100), width = 1, batch = batch)
        elementIndex = elementIndex + 1
    
    lastYPos = [0, 0]
    lastXPos = [0, 0]
    sampleCount = 0
    yCoord = 0
    minValue = channels[0]["peak"] + 1
    maxValue = (channels[0]["peak"] * -1) - 1

    ## Capture a window's worth of data points
    for i in range(iterCount):

        dataPoint = getSamples()       
        sampleCount = sampleCount + 1

        ## Apply offset
        dataX = dataPoint[0] + channels[0]["offset"]
        if dataX < minValue:
            minValue = dataX
        if dataX > maxValue:
            maxValue = dataX

        dataY = dataPoint[1] + channels[1]["offset"]

        ## If we're trying for a One Shot trigger and we haven't triggered yet and now have a data point above the trigger,
        ## remember where we triggered and fill 1/2 of the data buffer with samples
        if oneShot and channels[0]["triggerIndex"] < 0 and dataPoint >= channels[0]["trigger"]:
            savedDataIndex = channels[0]["dataIndex"]
            for i in range(int(len(channels[0]["dataBuffer"]) / 4)):
                dataPoint = getSamples()[0]
            
            channels[0]["triggerIndex"] = channels[0]["savedDataIndex"]
            channels[0]["oneShotHome"] = channels[0]["triggerIndex"]

            break

        ## If we're in XY mode, take samples as X and Y
        if xy:
            xPos = int(dataX / channels[0]["peak"] * channels[0]["scale"] * (window.width - 80))
            yPos = int(dataY / channels[0]["peak"] * channels[0]["scale"] * (window.height - 80))
            
            ## If our points are close enough, draw a line between them. Otherwise, use three little dots (rather than a circle) for performance
            threshold = window.width / 30
            if abs(lastXPos[0] - xPos) < threshold and abs(lastYPos[0] - yPos) < threshold:
                elements[elementIndex] = shapes.Line(lastXPos[0], lastYPos[0] + 40, xPos, yPos + 40, color = (120, 120, 220), width = 2, batch = batch)
                elementIndex = elementIndex + 1
            else:
                lineSize = int(window.width / 350)
                elements[elementIndex] = shapes.Line(xPos - lineSize, yPos + 40, xPos + lineSize, yPos + 40, color = (120, 120, 220), width = lineSize, batch = batch)
                elementIndex = elementIndex + 1

            lastXPos[0] = xPos
            lastYPos[0] = yPos
        else:
            ## Otherwise, take samples for a regular graph
            xPos = int(i * channels[0]["zoom"])
            yPos = int(dataX / channels[0]["peak"] * channels[0]["scale"] * (window.height - 80))
            
            if lastXPos[0] > 0:
                elements[elementIndex] = shapes.Line(lastXPos[0], lastYPos[0] + 40, xPos, yPos + 40, color = (120, 120, 220), width = 1, batch = batch)
            
            lastXPos[0] = xPos
            lastYPos[0] = yPos
            
            if channels[1]["input"] is not None:
                yPos = int(dataY / channels[1]["peak"] * channels[1]["scale"] * (window.height - 80))
                xPos = int(i * channels[1]["zoom"])

                if lastXPos[1] > 0:
                    elementIndex = elementIndex + 1
                    elements[elementIndex] = shapes.Line(lastXPos[1], lastYPos[1] + 40, xPos, yPos + 40, color = (120, 220, 120), width = 1, batch = batch)

                lastYPos[1] = yPos
                lastXPos[1] = xPos

            elementIndex = elementIndex + 1

    mouseFrameEnd = time.perf_counter()
    mouseFrameDuration = mouseFrameEnd - frameBegin
    
    offset = format(mousePos[0] / window.width * mouseFrameDuration, ".5f")
    dataValue = format(((mousePos[1] - 40) / (window.height - 80)) / channels[0]["scale"] * channels[0]["vref"], ".2f")
    vpp = format((maxValue - minValue) / channels[0]["peak"] * channels[0]["vref"], ".2f")

    anchor_x = 'left'
    if mousePos[0] > (window.width - 250):
        anchor_x = 'right'

    ## Measure time / voltage deltas via mouse dragging
    if mouseDragStart[0] != 0:
        startX = min(mouseDragStart[0], mousePos[0])
        startY = min(mouseDragStart[1], mousePos[1])
        width = abs(mousePos[0] - mouseDragStart[0]) + 1
        height = abs(mousePos[1] - mouseDragStart[1])

        dragRectangle = shapes.BorderedRectangle(startX, startY, width, height, border=1, color = (255, 255, 255), border_color = (255, 255, 255), batch = batch)
        dragRectangle.opacity = 100

        dxData = width / window.width * mouseFrameDuration
        dx = format(dxData, ".5f") + "s (" + format(1 / dxData, "5.2f") + "Hz)"
        dy = format(width * mouseFrameDuration, ".5f")
        anchor_x = 'center'
        dv = format(height / (window.height - 80) / channels[0]["scale"] * channels[0]["vref"], ".2f")
        mouseLabel = pyglet.text.Label('dt: ' + dx + ', dv: ' + dv + "v, Vpp: " +  vpp,
                                font_size=10,
                                x=window.width / 2,
                                y=20,
                                anchor_x=anchor_x,
                                anchor_y='bottom',
                                color=(255, 255, 255, 255),
                                batch = batch
                                )
    else:
        mouseLabel = pyglet.text.Label('time: ' + offset + ', value: ' + dataValue + "v, Vpp: " +  vpp,
                            font_size=10,
                            x=mousePos[0],
                            y=mousePos[1] + 5,
                            anchor_x=anchor_x,
                            anchor_y='bottom',
                            color=(255, 120, 120, 255),
                            batch = batch
                            )

    ## Clear the window and draw the screen
    window.clear()
    batch.draw()

    frameEnd = time.perf_counter()
    frameDuration = frameEnd - frameBegin

    global currentFrame
    currentFrame = (currentFrame + 1) % 1000

    ## Update the status
    if currentFrame % 10 == 0:
        waiting0 = 0
        waiting1 = 0

        if channels[0]["port"] is not None:
            waiting0 = channels[0]["port"].in_waiting

        if channels[1]["port"] is not None:
            waiting1 = channels[1]["port"].in_waiting

        print("Processing " + format(sampleCount / frameDuration, ">5.0f") +
            " samples per second (" + format(1 / frameDuration, ".1F") +
            " FPS, " + format(sampleCount, "3.0f") + " SPF. Buffers: " + format(waiting0, ">4.0f") + ", " + format(waiting1, ">4.0f") + ")", end = "\r")
   
pyglet.app.run()

if channels[0]["captureFile"] is not None:
    channels[0]["captureFile"].close()
if channels[1]["captureFile"] is not None:
    channels[1]["captureFile"].close()    
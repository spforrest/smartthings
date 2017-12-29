#!/usr/bin/env micropython

import socket
import json
import time
import math
import machine
import gc


LISTEN_ADDR = '0.0.0.0'
LISTEN_PORT = 8080
LED_R_PIN = 13
LED_G_PIN = 12
LED_B_PIN = 14
STATE = {
    'switch': 'off',
    'red': 253,
    'green': 248,
    'blue': 236,
    'hue': 0.0,
    'saturation': 0.0,
    'level': 100,
    'frequency': 1000,
    'fadetime': 1000,
}

LED_R = machine.PWM(machine.Pin(LED_R_PIN), freq=STATE['frequency'], duty=0)
LED_G = machine.PWM(machine.Pin(LED_G_PIN), freq=STATE['frequency'], duty=0)
LED_B = machine.PWM(machine.Pin(LED_B_PIN), freq=STATE['frequency'], duty=0)


def init_lights():
    if STATE['fadetime']:
        fadesteps = int(STATE['fadetime'] / 50.0)
        fadeduties = [int(math.sin((i+1) / fadesteps * math.pi) * 1023) for i in range(fadesteps)]
        fadedelay = 50
    else:
        fadeduties = [1023]
        fadedelay = 1000
    for i in (
        (LED_R, LED_G, LED_B),
        (LED_R,), (LED_G,), (LED_B,),
        (LED_R, LED_G), (LED_G, LED_B), (LED_R, LED_B),
        (LED_R, LED_G, LED_B)
    ):
        print('Testing: {}'.format(i))
        for fadeduty in fadeduties:
            for j in i:
                j.duty(fadeduty)
            time.sleep_ms(fadedelay)
        for j in i:
            j.duty(0)
    set_lights()


def set_lights():
    if STATE['switch'] == 'on':
        ledto_r = int((STATE['red'] / 255 * 1023) * (STATE['level'] / 100.0))
        ledto_g = int((STATE['green'] / 255 * 1023) * (STATE['level'] / 100.0))
        ledto_b = int((STATE['blue'] / 255 * 1023) * (STATE['level'] / 100.0))
    else:
        ledto_r = 0
        ledto_g = 0
        ledto_b = 0
    ledfrom_r = LED_R.duty()
    ledfrom_g = LED_G.duty()
    ledfrom_b = LED_B.duty()
    freq = STATE['frequency']
    if LED_R.freq() != freq:
        # Deinit all first, as all PWMs must be running at the
        # same frequency at the same time
        for i in (LED_R, LED_G, LED_B):
            print('{}.deinit()'.format(i))
            i.deinit()
        print('LED_R.init(freq={}, duty={})'.format(freq, ledfrom_r))
        LED_R.init(freq=freq, duty=ledfrom_r)
        print('LED_G.init(freq={}, duty={})'.format(freq, ledfrom_g))
        LED_G.init(freq=freq, duty=ledfrom_g)
        print('LED_B.init(freq={}, duty={})'.format(freq, ledfrom_b))
        LED_B.init(freq=freq, duty=ledfrom_b)

    if (ledfrom_r != ledto_r) or (ledfrom_g != ledto_g) or (ledfrom_b != ledto_b):
        print('PWM: Setting to R={}, G={}, B={}'.format(ledto_r, ledto_g, ledto_b))
        if STATE['fadetime']:
            fadesteps = int(STATE['fadetime'] / 50.0)
            fadeduties = [[
                (
                    ledto + ((ledfrom-ledto) - int(math.sin((fadestep+1) / (fadesteps*2) * math.pi) * (ledfrom-ledto)))
                ) for (ledfrom, ledto) in (
                    (ledfrom_r, ledto_r), (ledfrom_g, ledto_g), (ledfrom_b, ledto_b)
                )
            ] for fadestep in range(fadesteps)]
            fadedelay = 50
        else:
            fadeduties = [(ledto_r, ledto_g, ledto_b)]
            fadedelay = 0
        print('R,G,B fades: {}, {}ms'.format(fadeduties, fadedelay))

        for (r, g, b) in fadeduties:
            LED_R.duty(r)
            LED_G.duty(g)
            LED_B.duty(b)
            time.sleep_ms(fadedelay)


def parse_data(reqdata):
    j = json.loads(reqdata)
    for k in j:
        if j[k] is None:
            continue
        if k == 'fadetime' and j[k] > 0 and j[k] < 50:
            j[k] = 50
        STATE[k] = j[k]
    response = json.dumps(STATE).encode('ASCII')
    return response


def process_connection(cl, addr):
    print('New connection: {}'.format(addr))
    in_firstline = True
    in_dataarea = False
    good_request = False
    reqdata = b''
    content_length = 0
    cl_file = cl.makefile('rwb', 0)
    while True:
        if in_dataarea:
            reqdata = cl.recv(content_length)
            break
        line = cl_file.readline()
        if not line:
            break
        elif in_firstline:
            if not line.startswith(b'POST '):
                cl_file.write(b'HTTP/1.0 400 Bad Request\r\n\r\nBad Request\r\n')
                cl_file.close()
                cl.close()
                break
            in_firstline = False
            good_request = True
        elif line.startswith(b'Content-Length: '):
            content_length = int(line[16:-2])
        elif line == b'\r\n':
            in_dataarea = True
    if good_request:
        print('IN: {}'.format(reqdata))
        try:
            response = parse_data(reqdata)
        except:
            cl_file.write(b'HTTP/1.0 500 Internal Server Error\r\n\r\nInternal Server Error\r\n')
            cl_file.close()
            cl.close()
            return
        print('OUT: {}'.format(response))
        cl_file.write(b'HTTP/1.1 200 OK\r\n')
        cl_file.write(b'Content-Type: application/json; charset=utf-8\r\n')
        cl_file.write(b'Content-Length: ' + str(len(response)).encode('ASCII') + b'\r\n')
        cl_file.write(b'\r\n')
        cl_file.write(response)
        cl_file.close()
        cl.close()
        set_lights()


def main():
    init_lights()

    addr = socket.getaddrinfo(LISTEN_ADDR, LISTEN_PORT)[0][-1]
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(1)
    print('Listen: {}'.format(addr))

    while True:
        gc.collect()
        print('Memory free: {}'.format(gc.mem_free()))
        process_connection(*s.accept())
        print()


if __name__ == '__main__':
    main()

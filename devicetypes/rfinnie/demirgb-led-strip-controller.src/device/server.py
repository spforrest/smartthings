#!/usr/bin/env micropython

# DemiRGB ESP8266 server
# Copyright (C) 2018 Ryan Finnie
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.

import socket
import json
import time
import math
import machine
import gc


LISTEN_ADDR = '0.0.0.0'
LISTEN_PORT = 8080
AUTH_SECRET = None
SYSLOG_HOST = '10.9.8.1'
SYSLOG_ID = 'demirgb'
LED_R_PIN = 13
LED_G_PIN = 12
LED_B_PIN = 14
INIT_LIGHT_TEST = True
USE_HSV = True
STATE = {
    'switch': 'off',
    'red': 253,
    'green': 248,
    'blue': 236,
    'hex': '#FDF8EC',
    'hue': 11.7647,
    'saturation': 6.71937,
    'level': 100,
    'frequency': 100,
    'fadetime': 1000,
}

LED_R = machine.PWM(machine.Pin(LED_R_PIN), freq=STATE['frequency'], duty=0)
LED_G = machine.PWM(machine.Pin(LED_G_PIN), freq=STATE['frequency'], duty=0)
LED_B = machine.PWM(machine.Pin(LED_B_PIN), freq=STATE['frequency'], duty=0)
SYSLOG_SOCKET = None


def debug(text):
    print(text)
    if SYSLOG_SOCKET and text:
        SYSLOG_SOCKET.sendto(
            '<135>{} demirgb: {}'.format(SYSLOG_ID, text).encode('ASCII'),
            (SYSLOG_HOST, 514),
        )


def hsv_to_rgb(h, s, v):
    if s == 0.0:
        return (v, v, v)
    i = int(h*6.)  # assume int() truncates
    f = (h*6.)-i
    p, q, t = v*(1.-s), v*(1.-s*f), v*(1.-s*(1.-f))
    i %= 6
    if i == 0:
        return (v, t, p)
    elif i == 1:
        return (q, v, p)
    elif i == 2:
        return (p, v, t)
    elif i == 3:
        return (p, q, v)
    elif i == 4:
        return (t, p, v)
    elif i == 5:
        return (v, p, q)


def init_lights():
    if not INIT_LIGHT_TEST:
        set_lights()
        return
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
        debug('Testing: {}'.format(i))
        for fadeduty in fadeduties:
            for j in i:
                j.duty(fadeduty)
            time.sleep_ms(fadedelay)
        for j in i:
            j.duty(0)
    set_lights()


def demo_lights():
    for l in range(3):
        for i in range(40):
            r, g, b = hsv_to_rgb(i / 40, 1, 1)
            LED_R.duty(int(r * 1023))
            LED_G.duty(int(g * 1023))
            LED_B.duty(int(b * 1023))
            time.sleep_ms(50)
    set_lights()


def set_lights():
    if STATE['switch'] == 'on':
        if USE_HSV:
            r, g, b = hsv_to_rgb(STATE['hue'] / 100.0, STATE['saturation'] / 100.0, STATE['level'] / 100.0)
            ledto_r = int(r * 1023)
            ledto_g = int(g * 1023)
            ledto_b = int(b * 1023)
        else:
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
            debug('{}.deinit()'.format(i))
            i.deinit()
        debug('LED_R.init(freq={}, duty={})'.format(freq, ledfrom_r))
        LED_R.init(freq=freq, duty=ledfrom_r)
        debug('LED_G.init(freq={}, duty={})'.format(freq, ledfrom_g))
        LED_G.init(freq=freq, duty=ledfrom_g)
        debug('LED_B.init(freq={}, duty={})'.format(freq, ledfrom_b))
        LED_B.init(freq=freq, duty=ledfrom_b)

    if (ledfrom_r != ledto_r) or (ledfrom_g != ledto_g) or (ledfrom_b != ledto_b):
        debug('PWM: Setting to R={}, G={}, B={}'.format(ledto_r, ledto_g, ledto_b))
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
        debug('R,G,B fades: {}, {}ms'.format(fadeduties, fadedelay))

        for (r, g, b) in fadeduties:
            LED_R.duty(r)
            LED_G.duty(g)
            LED_B.duty(b)
            time.sleep_ms(fadedelay)


def parse_data(reqdata):
    j = json.loads(reqdata)
    if 'state' in j:
        for k in j['state']:
            if k not in STATE:
                continue
            if j['state'][k] is None:
                continue
            if k == 'fadetime' and j['state'][k] > 0 and j['state'][k] < 50:
                j['state'][k] = 50
            STATE[k] = j['state'][k]
    return j


def http_error(cl_file, cl, code, desc):
    debug('ERROR: {} ({})'.format(desc, code))
    cl_file.write(b'HTTP/1.0 {} {}\r\n\r\n{}\r\n'.format(code, desc, desc))
    cl_file.close()
    cl.close()


def process_connection(cl, addr):
    debug('New connection: {}'.format(addr))
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
                http_error(cl_file, cl, 400, 'Bad Request')
                break
            in_firstline = False
            good_request = True
        elif line.startswith(b'Content-Length: '):
            content_length = int(line[16:-2])
        elif line == b'\r\n':
            in_dataarea = True

    if not good_request:
        return
    debug('IN: {}'.format(reqdata))
    try:
        j = parse_data(reqdata)
    except:
        http_error(cl_file, cl, 500, 'Internal Server Error')
        return

    if AUTH_SECRET is not None:
        if ('auth' not in j) or (j['auth'] != AUTH_SECRET):
            http_error(cl_file, cl, 401, 'Unauthorized')
            return

    response = json.dumps({
        'state': STATE,
    }).encode('ASCII')
    debug('OUT: {}'.format(response))
    cl_file.write(b'HTTP/1.1 200 OK\r\n')
    cl_file.write(b'Content-Type: application/json; charset=utf-8\r\n')
    cl_file.write(b'Content-Length: ' + str(len(response)).encode('ASCII') + b'\r\n')
    cl_file.write(b'\r\n')
    cl_file.write(response)
    cl_file.close()
    cl.close()
    if 'cmd' in j:
        if j['cmd'] == 'reset':
            time.sleep(1)
            machine.reset()
            return
        if j['cmd'] == 'demo':
            demo_lights()
    set_lights()


def main():
    global SYSLOG_SOCKET

    if SYSLOG_HOST:
        SYSLOG_SOCKET = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    init_lights()

    addr = socket.getaddrinfo(LISTEN_ADDR, LISTEN_PORT)[0][-1]
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(addr)
    s.listen(1)
    debug('Listen: {}'.format(addr))

    while True:
        gc.collect()
        debug('Memory free: {}'.format(gc.mem_free()))
        process_connection(*s.accept())
        debug('')


if __name__ == '__main__':
    main()

import server


def recv(file='server.mpy', port=9999, reset=True):
    import usocket as socket
    import network
    import machine

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(socket.getaddrinfo('0.0.0.0', port)[0][-1])
    s.listen(1)

    sta_if = network.WLAN(network.STA_IF)
    print('Listening on port {}: {}'.format(port, sta_if.ifconfig()))

    (cl, addr) = s.accept()
    print('New connection: {}'.format(addr))
    f = open(file, 'w')
    written = 0
    while True:
        buf = cl.recv(1024)
        if not buf:
            break
        f.write(buf)
        written += len(buf)
    f.close()
    cl.close()
    s.close()
    print('{} bytes written to {}'.format(written, file))

    if reset:
        print('Resetting')
        machine.reset()


server.main()

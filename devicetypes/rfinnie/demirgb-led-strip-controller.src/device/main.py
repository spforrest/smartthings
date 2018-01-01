import server


def recv(*args, **kwargs):
    import uploader

    uploader.recv(*args, **kwargs)


server.main()

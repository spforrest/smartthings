all: server.mpy

%.mpy: %.py
	mpy-cross -v $<

clean:
	$(RM) *.mpy

upload: server.mpy
	nc -N 10.9.8.147 9999 < $<

.PHONY: upload

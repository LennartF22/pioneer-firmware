.PHONY: all clean

all: root-shell

clean:
	rm root-shell

root-shell:
	arm-linux-gnueabi-gcc -nostdlib -static root-shell.s -s -o root-shell

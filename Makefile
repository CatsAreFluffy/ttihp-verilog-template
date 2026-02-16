.PHONY: harden test

harden:
	PDK_ROOT=./pdk PDK=ihp-sg13g2 LIBRELANE_TAG=3.0.0.dev44 time ./tt/tt_tool.py --harden --ihp

test:
	make -C test -B
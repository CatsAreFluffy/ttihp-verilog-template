<!---

This file is used to generate your project datasheet. Please fill in the information below and delete any unused
sections.

You can also include images in this folder and reference them in the markdown. Each image must be less than
512 kb in size, and the combined size of all images must be less than 1 MB.
-->

## How it works

This is an implementation of a simple 4 bit CPU.

## How to test

The output and IO pins are used for the CPU's memory bus. uio[3:0] are used for data. If ui[5:4] isn't 3, then {uo, ui[7:4]} is a ROM address. Otherwise, uo is a RAM address, and ui[4] is low when writing and high when reading.

## External hardware

List external hardware used in your project (e.g. PMOD, LED display, etc), if any

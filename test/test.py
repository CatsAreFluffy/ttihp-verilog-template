# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, NextTimeStep, Timer

# Instructions
ldx = 0b010_00
ldy = 0b010_01
lda = 0b110_00
# Addressing modes
zi = 0b000
im = 0b100

def assemble(instructions):
    result = []
    for instr in instructions:
        opcode, mode, *operand = instr
        if len(operand):
            operand = operand[0]
        else:
            operand = 0
        instruction = (operand << 8) | (opcode << 3) | mode
        result.append(instruction & 15)
        result.append((instruction >> 4) & 15)
        result.append((instruction >> 8) & 15)
        result.append(0)
    return result

async def cycle(dut, rom=[], ram=[]):
    await Timer(50, unit="ns")
    if dut.uio_out.value[5:4] == 0b11:
        # RAM access
        address = int(dut.uo_out.value)
        await Timer(50, unit="ns")
        if dut.uio_out.value[6] == 0:
            ram[address] = int(dut.uio_out.value[3:0])
        dut._log.info("RAM")
        dut._log.info("%s %s %s", ram, address, ram[address])
        dut.uio_in.value = ram[address]
    else:
        address = int(dut.uo_out.value) * 16 + (int(dut.uio_out.value) >> 4)
        assert (address & 3) != 3
        await Timer(50, unit="ns")
        dut.uio_in.value = rom[address]
    await ClockCycles(dut.clk, 1)

@cocotb.test()
async def test_project(dut):
    dut._log.info("Start")

    # Set the clock period to 1 us (1 MHz)
    clock = Clock(dut.clk, 1, unit="us")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    dut.ui_in.value = 0
    dut.uio_in.value = 0
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1

    dut._log.info("Test instruction fetch")
    rom = [4, 12, 8, 0, 5, 7, 9, 0, 0, 0, 0, 0]
    for i in range(4): await cycle(dut, rom)
    assert dut.user_project.instr_1.value == 4
    assert dut.user_project.instr_2.value == 12
    assert dut.user_project.instr_3.value == 8
    for i in range(3): await cycle(dut, rom)
    assert dut.user_project.instr_1.value == 5
    assert dut.user_project.instr_2.value == 7
    assert dut.user_project.instr_3.value == 9

    dut._log.info("Test load immediate instructions")
    rom = assemble([(lda, im, 1), (ldx, im, 2), (ldy, im, 3), (0, 0, 0)])
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 1)
    dut.rst_n.value = 1
    for i in range(5): await cycle(dut, rom)
    assert dut.user_project.reg_a.value == 1
    for i in range(3): await cycle(dut, rom)
    assert dut.user_project.reg_x.value == 2
    for i in range(3): await cycle(dut, rom)
    assert dut.user_project.reg_y.value == 3

    dut._log.info("Test load from memory instructions")
    rom = assemble([(ldy, zi, 0), (ldx, zi, 1), (0, 0, 0)])
    ram = [4, 2]
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 1)
    dut.rst_n.value = 1
    for i in range(6): await cycle(dut, rom, ram)
    assert dut.user_project.reg_y.value == 4
    for i in range(4): await cycle(dut, rom, ram)
    assert dut.user_project.reg_x.value == 2

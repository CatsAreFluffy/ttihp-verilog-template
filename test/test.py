# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, NextTimeStep, Timer

# Instructions
nop  = 0b000_00
jz   = 0b000_01
js   = 0b000_10
jc   = 0b000_11
jmp  = 0b001_00
jnz  = 0b001_01
jns  = 0b001_10
jnc  = 0b001_11
ldx  = 0b010_00
ldy  = 0b010_01
addx = 0b010_10
addy = 0b010_11
stx  = 0b011_00
sty  = 0b011_01
lda  = 0b110_00
adda = 0b110_10
sta  = 0b111_00
suba = 0b111_10
# Addressing modes
zi = 0b000
ix = 0b001
yi = 0b010
yx = 0b011
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
        dut.uio_in.value = ram[address]
    else:
        address = int(dut.uo_out.value) * 16 + (int(dut.uio_out.value) >> 4)
        assert (address & 3) != 3
        await Timer(50, unit="ns")
        dut.uio_in.value = rom[address]
    await ClockCycles(dut.clk, 1)

async def next_instruction(dut, rom=[], ram=[]):
    await cycle(dut, rom, ram)
    cycles = 1
    while dut.user_project.instr_done.value == 0:
        await cycle(dut, rom, ram)
        cycles += 1
    return cycles

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
    assert dut.user_project.load_buffer.value == 8
    for i in range(3): await cycle(dut, rom)
    assert dut.user_project.instr_1.value == 5
    assert dut.user_project.instr_2.value == 7
    assert dut.user_project.load_buffer.value == 9

    dut._log.info("Test load immediate instructions")
    rom = assemble([(lda, im, 1), (ldx, im, 2), (ldy, im, 3), (0, 0, 0)])
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 1)
    dut.rst_n.value = 1
    await next_instruction(dut, rom)
    assert dut.user_project.reg_a.value == 1
    await next_instruction(dut, rom)
    assert dut.user_project.reg_x.value == 2
    await next_instruction(dut, rom)
    assert dut.user_project.reg_y.value == 3

    dut._log.info("Test load from memory instructions")
    rom = assemble([(ldy, zi, 0), (ldx, zi, 1), (0, 0, 0)])
    ram = [4, 2]
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 1)
    dut.rst_n.value = 1
    await next_instruction(dut, rom, ram)
    assert dut.user_project.reg_y.value == 4
    await next_instruction(dut, rom, ram)
    assert dut.user_project.reg_x.value == 2

    dut._log.info("Test store to memory instructions")
    rom = assemble([(lda, im, 5), (sta, zi, 0), (ldx, zi, 0), (0, 0, 0)])
    ram = [0]
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 1)
    dut.rst_n.value = 1
    for i in range(2): await next_instruction(dut, rom, ram)
    assert ram[0] == 5
    await next_instruction(dut, rom, ram)
    assert dut.user_project.reg_x.value == 5

    dut._log.info("Test jump instruction")
    rom = assemble([(lda, zi, 1), (sta, zi, 0), (lda, zi, 2), (sta, zi, 1), (jmp, zi, 0), (0, 0, 0)])
    ram = [3, 8, 4]
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 1)
    dut.rst_n.value = 1
    for i in range(5): await next_instruction(dut, rom, ram)
    assert ram == [8, 4, 4]
    assert dut.user_project.program_counter.value == 0
    for i in range(5): await next_instruction(dut, rom, ram)
    assert ram == [4, 4, 4]
    assert dut.user_project.program_counter.value == 0

    dut._log.info("Test indexed addressing")
    rom = assemble([(ldx, im, 1), (ldy, im, 2), (lda, ix, 8), (lda, yi, 8), (lda, yx, 8), (0, 0, 0)])
    ram = [0]*256
    ram[0x81] = 1
    ram[0x28] = 2
    ram[0x21] = 3
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 1)
    dut.rst_n.value = 1
    for i in range(3): await next_instruction(dut, rom, ram)
    assert dut.user_project.reg_a.value == 1
    await next_instruction(dut, rom, ram)
    assert dut.user_project.reg_a.value == 2
    await next_instruction(dut, rom, ram)
    assert dut.user_project.reg_a.value == 3

    dut._log.info("Test addition and subtraction")
    rom = assemble([(lda, im, 5), (adda, im, 3), (lda, im, 5), (suba, im, 3), (0, 0, 0)])
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 1)
    dut.rst_n.value = 1
    for i in range(2): await next_instruction(dut, rom, ram)
    assert dut.user_project.reg_a.value == 8
    for i in range(2): await next_instruction(dut, rom, ram)
    assert dut.user_project.reg_a.value == 2

    dut._log.info("Test flags")
    rom = assemble([(lda, im, 1), (adda, im, 2), (lda, im, 3), (adda, im, 5), (lda, im, 10), (adda, im, 10), (lda, im, 3), (suba, im, 3), (lda, im, 2), (suba, im, 3), (0, 0, 0)])
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 1)
    dut.rst_n.value = 1
    for i in range(2): await next_instruction(dut, rom, ram)
    assert dut.user_project.zero_flag.value == 0
    assert dut.user_project.sign_flag.value == 0
    assert dut.user_project.carry_flag.value == 0
    for i in range(2): await next_instruction(dut, rom, ram)
    assert dut.user_project.zero_flag.value == 0
    assert dut.user_project.sign_flag.value == 1
    assert dut.user_project.carry_flag.value == 0
    for i in range(2): await next_instruction(dut, rom, ram)
    assert dut.user_project.zero_flag.value == 0
    assert dut.user_project.sign_flag.value == 0
    assert dut.user_project.carry_flag.value == 1
    for i in range(2): await next_instruction(dut, rom, ram)
    assert dut.user_project.zero_flag.value == 1
    assert dut.user_project.sign_flag.value == 0
    assert dut.user_project.carry_flag.value == 1
    for i in range(2): await next_instruction(dut, rom, ram)
    assert dut.user_project.zero_flag.value == 0
    assert dut.user_project.sign_flag.value == 1
    assert dut.user_project.carry_flag.value == 0

    dut._log.info("Test branches")
    rom = assemble([(lda, im, 0), (ldx, im, 3), (nop, zi, 0), (nop, zi, 0), (adda, im, 2), (addx, im, 15), (jnz, zi, 1), (0, 0, 0)])
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 1)
    dut.rst_n.value = 1
    for i in range(4+3): await next_instruction(dut, rom, ram)
    assert dut.user_project.program_counter.value == 4
    for i in range(3*2): await next_instruction(dut, rom, ram)
    assert dut.user_project.program_counter.value == 7

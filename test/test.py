# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, NextTimeStep, Timer


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
    rom = [4, 8, 12, 0, 1, 3, 5, 0, 9, 11, 13, 0, 2, 6, 10, 0]
    for i in range(4):
        await Timer(50, unit="ns")
        address = int(dut.uo_out.value) * 16 + (int(dut.uio_out.value) >> 4)
        assert (address & 3) != 3
        await Timer(50, unit="ns")
        dut.uio_in.value = rom[address]
        await ClockCycles(dut.clk, 1)
    assert dut.user_project.instr_1.value == 4
    assert dut.user_project.instr_2.value == 8
    assert dut.user_project.instr_3.value == 12
    for i in range(3):
        await Timer(50, unit="ns")
        address = int(dut.uo_out.value) * 16 + (int(dut.uio_out.value) >> 4)
        assert (address & 3) != 3
        await Timer(50, unit="ns")
        dut.uio_in.value = rom[address]
        await ClockCycles(dut.clk, 1)
    assert dut.user_project.instr_1.value == 1
    assert dut.user_project.instr_2.value == 3
    assert dut.user_project.instr_3.value == 5

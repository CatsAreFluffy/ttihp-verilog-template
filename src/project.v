/*
 * Copyright (c) 2026 CatsAreFluffy
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module tt_um_CatsAreFluffy (
    input  wire [7:0] ui_in,    // Dedicated inputs
    output reg  [7:0] uo_out,   // Dedicated outputs
    input  wire [7:0] uio_in,   // IOs: Input path
    output reg  [7:0] uio_out,  // IOs: Output path
    output reg  [7:0] uio_oe,   // IOs: Enable path (active high: 0=input, 1=output)
    input  wire       ena,      // always 1 when the design is powered, so you can ignore it
    input  wire       clk,      // clock
    input  wire       rst_n     // reset_n - low to reset
);

  // List all unused inputs to prevent warnings
  wire _unused = &{ui_in, uio_in[7:4], ena, 1'b0};


  // Internal states
  localparam FETCH1_BIT = 0;
  localparam FETCH2_BIT = 1;
  localparam FETCH3_BIT = 2;
  localparam LOAD_BIT   = 3;
  localparam STORE_BIT  = 4;

  localparam FETCH1 = 1 << FETCH1_BIT;
  localparam FETCH2 = 1 << FETCH2_BIT;
  localparam FETCH3 = 1 << FETCH3_BIT;
  localparam LOAD   = 1 << LOAD_BIT;
  localparam STORE  = 1 << STORE_BIT;

  (* onehot *)
  reg [4:0] state;

  reg [9:0] program_counter;

  // CPU registers
  reg [3:0] reg_a;
  reg [3:0] reg_x;
  reg [3:0] reg_y;

  reg [3:0] instr_1;
  reg [3:0] instr_2;
  reg [3:0] instr_3;

  // Instruction fields
  wire [2:0] mode = instr_1[2:0];
  wire [1:0] column = {instr_2[0], instr_1[3]};
  wire [2:0] row = instr_2[3:1];
  wire [3:0] immediate = instr_3;

  // Control lines
  wire jump_instr = !row[2] && !row[1];
  wire store_instr = row[1] && row[0] && !column[1];

  wire in2_from_memory = !mode[2];

  wire set_a = row[2];
  wire set_x = !row[2] && !row[0] && !column[0];
  wire set_y = !row[2] && !row[0] && column[0];

  reg [3:0] alu_in1;
  reg [3:0] alu_in2;

  reg [3:0] load_buffer;

  // Logic for outputs
  always_comb begin
    case (state)
      LOAD: begin
        uo_out = 8'(immediate);
        uio_out = 8'b01110000;
        uio_oe = 8'b11110000;
      end
      STORE: begin
        uo_out = 8'(immediate);
        uio_out = {4'b0011, alu_in1};
        uio_oe = 8'b11111111;
      end
      default: begin
        // Fetch
        uo_out = program_counter[9:2];
        uio_out[7:6] = program_counter[1:0];
        uio_out[5] = state[FETCH3_BIT];
        uio_out[4] = state[FETCH2_BIT];
        uio_out[3:0] = 0;
        uio_oe = 8'b11110000;
      end
    endcase
  end

  // Update logic for state
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      state <= FETCH1;
    end else begin
      case (state)
        FETCH1: state <= FETCH2;
        FETCH2: state <= FETCH3;
        FETCH3: begin
          if (store_instr) begin
            state <= STORE;
          end else if (jump_instr) begin
            state <= FETCH1;
          end else if (in2_from_memory) begin
            state <= LOAD;
          end else begin
            state <= FETCH1;
          end
        end
        // LOAD and STORE
        default: state <= FETCH1;
      endcase
    end
  end

  // Update logic for program counter
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      program_counter <= 0;
    end else if (state == FETCH3) begin
      if (jump_instr) program_counter <= {4'b0000, uio_in[3:0], 2'b00};
      else            program_counter <= program_counter + 1;
    end
  end

  // Update logic for registers
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      reg_a <= 0;
      reg_x <= 0;
      reg_y <= 0;
    end else if (state == FETCH1) begin
      if (set_a) reg_a <= alu_in2;
      if (set_x) reg_x <= alu_in2;
      if (set_y) reg_y <= alu_in2;
    end
  end

  // Update logic for instr_*
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      instr_1 <= 0;
      instr_2 <= 0;
      instr_3 <= 0;
    end else begin
      case (state)
        FETCH1: instr_1 <= uio_in[3:0];
        FETCH2: instr_2 <= uio_in[3:0];
        FETCH3: instr_3 <= uio_in[3:0];
      endcase
    end
  end

  // Logic for alu_in1
  always_comb begin
    if (row[2])        alu_in1 = reg_a;
    else if(column[0]) alu_in1 = reg_y;
    else               alu_in1 = reg_x;
  end

  // Logic for alu_in2
  always_comb begin
    case (mode)
      3'b100:  alu_in2 = immediate;
      default: alu_in2 = load_buffer;
    endcase
  end

  // Update logic for load_buffer
  always_ff @(posedge clk or negedge rst_n) begin
    if (!rst_n) begin
      load_buffer <= 0;
    end else if (state == LOAD) begin
      load_buffer <= uio_in[3:0];
    end
  end

  // Nice things for simulation
  `ifndef SYNTHESIS
    wire [32*4*8-1:0] mnemonics = {
      "    ", "    ", "    ", "    ",
      " jmp", "    ", "    ", "    ",
      " ldx", " ldy", "    ", "    ",
      " stx", " sty", "    ", "    ",
      "    ", "    ", "    ", "    ",
      "    ", "    ", "    ", "    ",
      " lda", "    ", "    ", "    ",
      " sta", "    ", "    ", "    "
    };

    wire [8*2*8-1:0] modenames = {
      "zi", "  ", "  ", "  ", "im", "  ", "  ", "  "
    };

    wire [31:0] mnemonic = 32'(mnemonics >> (31 - {row, column})*32);

    wire [15:0] modename = 16'(modenames >> (7 - 5'(mode))*16);

    wire [7:0] immediate_string = uio_in[3:0] < 10 ? "0" + 8'(uio_in[3:0]) : "a" + 8'(uio_in[3:0]) - 10;

    reg [(4+1+2+1+1)*8-1:0] instr_string;

    always_latch begin
      if (state == FETCH3) begin
        instr_string = {mnemonic, " ", modename, " ", immediate_string};
      end
    end

    reg [6*8-1:0] state_string;

    always_comb begin
      case (state)
        FETCH1:  state_string = "FETCH1";
        FETCH2:  state_string = "FETCH2";
        FETCH3:  state_string = "FETCH3";
        LOAD:    state_string = "LOAD  ";
        STORE:   state_string = "STORE ";
        default: state_string = "??????";
      endcase
    end

    wire _unused_sim_only = &{instr_string, state_string};
  `endif

endmodule

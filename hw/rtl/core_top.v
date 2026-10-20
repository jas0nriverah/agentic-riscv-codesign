// Stock PicoRV32 configured for rv32im, with its native memory port exposed.
// Adapted from the ML branch's hardware/core_top.v with the CRC32 PCPI unit removed.
// FUSED=1 adds the PROVISIONAL dry-run PCPI unit (pcpi_fused.v); the default FUSED=0
// is the stock core. The ports are the same either way so the frozen PCF applies.
module core_top #(
    parameter FUSED = 0
) (
    input clk, resetn,
    output trap, mem_valid, mem_instr,
    input mem_ready,
    output [31:0] mem_addr, mem_wdata,
    output [3:0] mem_wstrb,
    input [31:0] mem_rdata
);
    wire pcpi_valid, pcpi_wr, pcpi_wait, pcpi_ready;
    wire [31:0] pcpi_insn, pcpi_rs1, pcpi_rs2, pcpi_rd;
    picorv32 #(
        .ENABLE_COUNTERS(1), .ENABLE_COUNTERS64(0),
        .ENABLE_REGS_16_31(1), .ENABLE_REGS_DUALPORT(1),
        .LATCHED_MEM_RDATA(0), .TWO_STAGE_SHIFT(1), .BARREL_SHIFTER(0),
        .TWO_CYCLE_COMPARE(0), .TWO_CYCLE_ALU(0), .COMPRESSED_ISA(0),
        .CATCH_MISALIGN(1), .CATCH_ILLINSN(1),
        // rv32im: the built-in sequential multiplier and divider
        .ENABLE_PCPI(FUSED != 0), .ENABLE_MUL(1), .ENABLE_FAST_MUL(0), .ENABLE_DIV(1),
        .ENABLE_IRQ(0), .ENABLE_TRACE(0), .REGS_INIT_ZERO(1),
        // same memory map as main's Spike setup: 16 MiB of RAM at 0x80000000
        .PROGADDR_RESET(32'h8000_0000), .STACKADDR(32'h8100_0000)
    ) cpu (
        .clk(clk), .resetn(resetn), .trap(trap),
        .mem_valid(mem_valid), .mem_instr(mem_instr), .mem_ready(mem_ready),
        .mem_addr(mem_addr), .mem_wdata(mem_wdata), .mem_wstrb(mem_wstrb),
        .mem_rdata(mem_rdata),
        .pcpi_valid(pcpi_valid), .pcpi_insn(pcpi_insn), .pcpi_rs1(pcpi_rs1), .pcpi_rs2(pcpi_rs2),
        .pcpi_wr(pcpi_wr), .pcpi_rd(pcpi_rd), .pcpi_wait(pcpi_wait), .pcpi_ready(pcpi_ready),
        .irq(32'b0)
    );
    generate if (FUSED != 0) begin : fused
        pcpi_fused unit (
            .clk(clk), .resetn(resetn), .valid(pcpi_valid),
            .insn(pcpi_insn), .rs1(pcpi_rs1), .rs2(pcpi_rs2),
            .wr(pcpi_wr), .wait_req(pcpi_wait), .ready(pcpi_ready), .rd(pcpi_rd)
        );
    end else begin : stock
        assign pcpi_wr = 1'b0;
        assign pcpi_rd = 32'b0;
        assign pcpi_wait = 1'b0;
        assign pcpi_ready = 1'b0;
    end endgenerate
endmodule

// The synthesized DUT contains the processor and extension, with external RAM.
module core_top #(
    parameter EXTENSION_MASK = 3,
    parameter PCPI_LATENCY = 1
) (
    input clk, resetn,
    output trap, mem_valid, mem_instr,
    input mem_ready,
    output [31:0] mem_addr, mem_wdata,
    output [3:0] mem_wstrb,
    input [31:0] mem_rdata,
    output debug_pcpi_valid, debug_pcpi_ready, debug_pcpi_wait
);
    wire [31:0] insn, rs1, rs2, rd;
    wire wr;
    picorv32 #(
        .ENABLE_COUNTERS(1), .ENABLE_COUNTERS64(0),
        .ENABLE_REGS_16_31(1), .ENABLE_REGS_DUALPORT(1),
        .LATCHED_MEM_RDATA(0), .TWO_STAGE_SHIFT(1), .BARREL_SHIFTER(0),
        .TWO_CYCLE_COMPARE(0), .TWO_CYCLE_ALU(0), .COMPRESSED_ISA(0),
        .CATCH_MISALIGN(1), .CATCH_ILLINSN(1),
        .ENABLE_PCPI(EXTENSION_MASK != 0), .ENABLE_MUL(0),
        .ENABLE_FAST_MUL(0), .ENABLE_DIV(0), .ENABLE_IRQ(0),
        .ENABLE_TRACE(0), .REGS_INIT_ZERO(1),
        .PROGADDR_RESET(0), .STACKADDR(32'h00010000)
    ) cpu (
        .clk(clk), .resetn(resetn), .trap(trap),
        .mem_valid(mem_valid), .mem_instr(mem_instr), .mem_ready(mem_ready),
        .mem_addr(mem_addr), .mem_wdata(mem_wdata), .mem_wstrb(mem_wstrb),
        .mem_rdata(mem_rdata), .pcpi_valid(debug_pcpi_valid),
        .pcpi_insn(insn), .pcpi_rs1(rs1), .pcpi_rs2(rs2),
        .pcpi_wr(wr), .pcpi_rd(rd), .pcpi_wait(debug_pcpi_wait),
        .pcpi_ready(debug_pcpi_ready), .irq(32'b0)
    );
    generate if (EXTENSION_MASK != 0) begin
        pcpi_candidates #(.MASK(EXTENSION_MASK), .LATENCY(PCPI_LATENCY)) extension (
            .clk(clk), .resetn(resetn), .valid(debug_pcpi_valid),
            .insn(insn), .rs1(rs1), .rs2(rs2), .rd(rd),
            .wr(wr), .wait_req(debug_pcpi_wait), .ready(debug_pcpi_ready)
        );
    end else begin
        assign wr = 0;
        assign rd = 0;
        assign debug_pcpi_wait = 0;
        assign debug_pcpi_ready = 0;
    end endgenerate
endmodule

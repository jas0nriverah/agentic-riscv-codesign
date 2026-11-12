// PROVISIONAL dry-run PCPI unit: one fused instruction on custom-0.
// custom-0 (0x0b), R-type, funct7=2, funct3=0: rd = cx_crc32_xoridx(rs1, rs2)
//   = ((rs1 ^ rs2) & 255) << 2
// Adapted from the ML branch's hardware/pcpi_single.v (origin/ai-guided-ml @ 7431a54):
// the result is captured on the first valid edge and acknowledged on the next cycle.
// Every other encoding is left alone, so PicoRV32's PCPI timeout still traps on it.
module pcpi_fused (
    input clk, resetn, valid,
    input [31:0] insn, rs1, rs2,
    output wr, wait_req, ready,
    output [31:0] rd
);
    wire recognized = valid && (insn & 32'hfe00707f) == 32'h0400000b;
    wire [31:0] value;
    cx_crc32_xoridx datapath(.in0(rs1), .in1(rs2), .result(value));
    reg active;
    reg [31:0] result;
    always @(posedge clk) begin
        if (!resetn || !valid) begin
            active <= 0;
            result <= 0;
        end else if (recognized && !active) begin
            result <= value;
            active <= 1;
        end
    end
    assign ready = recognized && active;
    assign wr = ready;
    assign wait_req = recognized && !ready;
    assign rd = result;
endmodule

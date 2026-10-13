// Two exact formulas extracted from the measured Embench crc32 kernel.
// custom-0, funct7=1, funct3=0: ((rs1 ^ rs2) & 255) << 2
// custom-0, funct7=1, funct3=1: rs1 ^ (rs2 >> 8)
module pcpi_candidates #(
    parameter MASK = 3,
    parameter LATENCY = 1
) (
    input clk, resetn, valid,
    input [31:0] insn, rs1, rs2,
    output wr, wait_req, ready,
    output [31:0] rd
);
    wire op0 = MASK[0] && (insn & 32'hfe00707f) == 32'h0200000b;
    wire op1 = MASK[1] && (insn & 32'hfe00707f) == 32'h0200100b;
    wire recognized = valid && (op0 || op1);
    wire [31:0] value = op0 ? {22'b0, (rs1[7:0] ^ rs2[7:0]), 2'b0}
                                 : (rs1 ^ (rs2 >> 8));
    generate if (LATENCY == 0) begin
        assign ready = recognized;
        assign rd = value;
    end else begin
        reg active;
        reg [31:0] remaining;
        reg [31:0] result;
        always @(posedge clk) begin
            if (!resetn || !valid) begin
                active <= 0;
                remaining <= 0;
                result <= 0;
            end else if (recognized && !active) begin
                active <= 1;
                remaining <= LATENCY - 1;
                result <= value;
            end else if (active && remaining != 0) begin
                remaining <= remaining - 1;
            end
        end
        assign ready = recognized && active && remaining == 0;
        assign rd = result;
    end endgenerate
    assign wr = ready;
    // Assert immediately on decode, including for responses beyond PCPI timeout.
    assign wait_req = recognized && !ready;
endmodule

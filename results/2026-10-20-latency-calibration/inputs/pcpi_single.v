// One fixed custom-0 instruction. Datapath changes cannot alter this contract.
// Capture at the first valid edge, acknowledge on the following cycle.
module pcpi_candidates #(parameter MASK = 1, parameter LATENCY = 1) (
    input clk, resetn, valid,
    input [31:0] insn, rs1, rs2,
    output wr, wait_req, ready,
    output [31:0] rd
);
    wire recognized = MASK != 0 && valid &&
                      (insn & 32'hfe00707f) == 32'h0200000b;
    wire [31:0] value;
    candidate datapath(.in0(rs1), .in1(rs2), .result(value));
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

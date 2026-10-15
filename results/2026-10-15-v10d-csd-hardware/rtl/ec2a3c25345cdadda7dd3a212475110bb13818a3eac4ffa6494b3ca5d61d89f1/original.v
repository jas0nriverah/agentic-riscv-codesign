module candidate(input wire [31:0] in0, in1, output wire [31:0] result);
wire [31:0] n0 = 32'h00000000 + 32'h00000154;
wire [31:0] n1 = in0 * n0;
wire [31:0] n2 = n1 + in1;
assign result = n2;
endmodule

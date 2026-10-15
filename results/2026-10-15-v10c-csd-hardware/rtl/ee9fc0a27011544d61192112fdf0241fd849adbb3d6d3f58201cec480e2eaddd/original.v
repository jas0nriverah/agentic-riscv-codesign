module candidate(input wire [31:0] in0, in1, output wire [31:0] result);
wire [31:0] n0 = in0 & 32'h0000003f;
wire [31:0] n1 = n0 - in1;
wire [31:0] n2 = 32'h00000000 + 32'h00000554;
wire [31:0] n3 = n1 * n2;
assign result = n3;
endmodule

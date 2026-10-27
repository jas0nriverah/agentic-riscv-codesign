module candidate(input wire [31:0] in0, in1, output wire [31:0] result);
wire [31:0] n0 = in0 & 32'h00000001;
wire [31:0] n1 = in1 & 32'h00000001;
wire [31:0] n2 = n0 + n1;
assign result = n2;
endmodule

module candidate(input wire [31:0] in0, in1, output wire [31:0] result);
wire [31:0] n0 = in0 + in1;
assign result = n0;
endmodule

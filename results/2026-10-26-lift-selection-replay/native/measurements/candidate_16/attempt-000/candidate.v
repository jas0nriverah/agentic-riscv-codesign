module candidate(input wire [31:0] in0, in1, output wire [31:0] result);
wire [31:0] n0 = in0 + in1;
wire [31:0] n1 = {31'b0, (32'h00000000 < n0)};
assign result = n1;
endmodule

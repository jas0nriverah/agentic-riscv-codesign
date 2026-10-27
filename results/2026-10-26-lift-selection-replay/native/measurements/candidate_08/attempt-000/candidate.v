module candidate(input wire [31:0] in0, in1, output wire [31:0] result);
wire [31:0] n0 = in0 + in1;
wire [31:0] n1 = {31'b0, ($signed(n0) < $signed(32'h00000002))};
assign result = n1;
endmodule

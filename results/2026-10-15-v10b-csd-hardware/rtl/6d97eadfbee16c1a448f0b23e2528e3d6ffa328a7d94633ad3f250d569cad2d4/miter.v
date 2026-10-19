module original_arm(input wire [31:0] in0, in1, output wire [31:0] result);
wire [31:0] n0 = in0 & 32'h0000003f;
wire [31:0] n1 = n0 - in1;
wire [31:0] n2 = 32'h00000000 + 32'h000001ff;
wire [31:0] n3 = n1 * n2;
assign result = n3;
endmodule
module csd_arm(input wire [31:0] in0, in1, output wire [31:0] result);
wire [31:0] n0 = in0 & 32'h0000003f;
wire [31:0] n1 = n0 - in1;
wire [31:0] shift_n2 = 32'h00000009;
wire [31:0] value_n2 = n1;
wire [31:0] stage_n2_0 = shift_n2[0] ? {value_n2[30:0], 1'b0} : value_n2;
wire [31:0] stage_n2_1 = shift_n2[1] ? {stage_n2_0[29:0], 2'b0} : stage_n2_0;
wire [31:0] stage_n2_2 = shift_n2[2] ? {stage_n2_1[27:0], 4'b0} : stage_n2_1;
wire [31:0] stage_n2_3 = shift_n2[3] ? {stage_n2_2[23:0], 8'b0} : stage_n2_2;
wire [31:0] stage_n2_4 = shift_n2[4] ? {stage_n2_3[15:0], 16'b0} : stage_n2_3;
wire [31:0] n2 = stage_n2_4;
wire [31:0] n3 = n2 - n1;
assign result = n3;
endmodule
module pair_miter(input wire [31:0] in0, in1, output wire trigger);
wire [31:0] original_result, csd_result;
original_arm original_instance(.in0(in0), .in1(in1), .result(original_result));
csd_arm csd_instance(.in0(in0), .in1(in1), .result(csd_result));
assign trigger = |(original_result ^ csd_result);
endmodule

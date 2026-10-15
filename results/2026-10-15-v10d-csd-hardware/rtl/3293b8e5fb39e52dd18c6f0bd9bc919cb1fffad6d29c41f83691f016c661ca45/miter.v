module original_arm(input wire [31:0] in0, in1, output wire [31:0] result);
wire [31:0] n0 = 32'h00000000 + 32'h000001ff;
wire [31:0] n1 = in0 * n0;
wire [31:0] n2 = n1 + in1;
assign result = n2;
endmodule
module csd_arm(input wire [31:0] in0, in1, output wire [31:0] result);
wire [31:0] shift_n0 = 32'h00000009;
wire [31:0] value_n0 = in0;
wire [31:0] stage_n0_0 = shift_n0[0] ? {value_n0[30:0], 1'b0} : value_n0;
wire [31:0] stage_n0_1 = shift_n0[1] ? {stage_n0_0[29:0], 2'b0} : stage_n0_0;
wire [31:0] stage_n0_2 = shift_n0[2] ? {stage_n0_1[27:0], 4'b0} : stage_n0_1;
wire [31:0] stage_n0_3 = shift_n0[3] ? {stage_n0_2[23:0], 8'b0} : stage_n0_2;
wire [31:0] stage_n0_4 = shift_n0[4] ? {stage_n0_3[15:0], 16'b0} : stage_n0_3;
wire [31:0] n0 = stage_n0_4;
wire [31:0] n1 = n0 - in0;
wire [31:0] n2 = n1 + in1;
assign result = n2;
endmodule
module pair_miter(input wire [31:0] in0, in1, output wire trigger);
wire [31:0] original_result, csd_result;
original_arm original_instance(.in0(in0), .in1(in1), .result(original_result));
csd_arm csd_instance(.in0(in0), .in1(in1), .result(csd_result));
assign trigger = |(original_result ^ csd_result);
endmodule

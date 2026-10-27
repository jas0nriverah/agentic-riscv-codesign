// Complete small FPGA SoC: PicoRV32, PCPI unit, initialized synchronous RAM,
// and a synchronous one-bit result stream (one word = 32 valid clock edges).
module soc_top #(
    parameter EXTENSION_MASK = 3,
    parameter FIRMWARE_FILE = "/Users/jasonrivera/Documents/Codex/2026-10-19/clo/agentic-riscv-codesign/generated/tacle-lift-cfg-tail-2026-10-25/measurements/candidate_15/attempt-000/firmware/firmware.hex"
) (
    input clk, resetn,
    output trap,
    output reg done, passed, fault,
    output report_strobe, report_bit
);
    wire mem_valid /* verilator public_flat_rd */, mem_instr;
    wire [31:0] mem_addr /* verilator public_flat_rd */, mem_wdata;
    wire [3:0] mem_wstrb /* verilator public_flat_rd */;
    reg mem_ready /* verilator public_flat_rd */;
    wire [31:0] mem_rdata;
    wire pcpi_valid /* verilator public_flat_rd */;
    wire pcpi_ready /* verilator public_flat_rd */;
    wire pcpi_wait /* verilator public_flat_rd */;
    wire [31:0] pcpi_insn, pcpi_rs1, pcpi_rs2, pcpi_rd;
    wire pcpi_wr;

    picorv32 #(
        .ENABLE_COUNTERS(1), .ENABLE_COUNTERS64(0),
        .ENABLE_REGS_16_31(1), .ENABLE_REGS_DUALPORT(1),
        .LATCHED_MEM_RDATA(0), .TWO_STAGE_SHIFT(1), .BARREL_SHIFTER(0),
        .TWO_CYCLE_COMPARE(0), .TWO_CYCLE_ALU(0), .COMPRESSED_ISA(0),
        .CATCH_MISALIGN(1), .CATCH_ILLINSN(1),
        .ENABLE_PCPI(EXTENSION_MASK != 0), .ENABLE_MUL(0),
        .ENABLE_FAST_MUL(0), .ENABLE_DIV(0), .ENABLE_IRQ(0),
        .ENABLE_TRACE(0), .REGS_INIT_ZERO(1),
        .PROGADDR_RESET(0), .STACKADDR(32'h00002000)
    ) cpu (
        .clk(clk), .resetn(resetn), .trap(trap),
        .mem_valid(mem_valid), .mem_instr(mem_instr), .mem_ready(mem_ready),
        .mem_addr(mem_addr), .mem_wdata(mem_wdata), .mem_wstrb(mem_wstrb),
        .mem_rdata(mem_rdata), .pcpi_valid(pcpi_valid), .pcpi_insn(pcpi_insn),
        .pcpi_rs1(pcpi_rs1), .pcpi_rs2(pcpi_rs2), .pcpi_wr(pcpi_wr),
        .pcpi_rd(pcpi_rd), .pcpi_wait(pcpi_wait), .pcpi_ready(pcpi_ready), .irq(32'b0)
    );
    generate if (EXTENSION_MASK != 0) begin
        pcpi_candidates #(.MASK(EXTENSION_MASK), .LATENCY(1)) extension (
            .clk(clk), .resetn(resetn), .valid(pcpi_valid), .insn(pcpi_insn),
            .rs1(pcpi_rs1), .rs2(pcpi_rs2), .rd(pcpi_rd), .wr(pcpi_wr),
            .wait_req(pcpi_wait), .ready(pcpi_ready)
        );
    end else begin
        assign pcpi_wr = 0;
        assign pcpi_rd = 0;
        assign pcpi_wait = 0;
        assign pcpi_ready = 0;
    end endgenerate

    // 8192 bytes = 2048 x 32-bit words; byte masks preserve native stores.
    // Full initialization includes .data and zero-filled unused/stack/BSS RAM.
    reg [31:0] memory [0:2047];
    reg [31:0] ram_rdata;
    initial $readmemh(FIRMWARE_FILE, memory);
    wire ram_access = mem_addr < 32'h00002000;
    wire request = resetn && mem_valid && !mem_ready;
    always @(posedge clk) begin
        if (request && ram_access) begin
            ram_rdata <= memory[mem_addr[12:2]];
            if (mem_wstrb[0]) memory[mem_addr[12:2]][7:0] <= mem_wdata[7:0];
            if (mem_wstrb[1]) memory[mem_addr[12:2]][15:8] <= mem_wdata[15:8];
            if (mem_wstrb[2]) memory[mem_addr[12:2]][23:16] <= mem_wdata[23:16];
            if (mem_wstrb[3]) memory[mem_addr[12:2]][31:24] <= mem_wdata[31:24];
        end
    end
    assign mem_rdata = ram_access ? ram_rdata : 32'b0;

    reg [31:0] report_shift;
    reg [5:0] report_remaining;
    assign report_strobe = report_remaining != 0;
    assign report_bit = report_shift[0];
    always @(posedge clk) begin
        mem_ready <= 0;
        if (!resetn) begin
            done <= 0;
            passed <= 0;
            fault <= 0;
            report_shift <= 0;
            report_remaining <= 0;
        end else begin
            if (report_remaining != 0) begin
                report_remaining <= report_remaining - 1;
                report_shift <= report_shift >> 1;
            end
            if (request) begin
                if (ram_access) begin
                    // Ready and synchronous read data become visible together.
                    mem_ready <= 1;
                end else if (mem_addr == 32'h10000000 && mem_wstrb == 4'b1111) begin
                    if (report_remaining == 0) begin
                        report_shift <= mem_wdata;
                        report_remaining <= 32;
                        mem_ready <= 1;
                    end
                end else if (mem_addr == 32'h10000004 && mem_wstrb == 4'b1111) begin
                    done <= 1;
                    passed <= mem_wdata == 32'h600d600d;
                    mem_ready <= 1;
                end else begin
                    fault <= 1;
                    done <= 1;
                    passed <= 0;
                    mem_ready <= 1;
                end
            end
        end
    end
endmodule

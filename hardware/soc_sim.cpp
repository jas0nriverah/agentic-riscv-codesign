#include "Vsoc_top.h"
#include "Vsoc_top___024root.h"
#include "verilated.h"
#include <cstdint>
#include <cstdio>
#include <vector>
int main(int argc, char **argv) {
    Verilated::commandArgs(argc, argv);
    Vsoc_top dut;
    std::vector<uint32_t> words;
    uint64_t accepted=0, valid_cycles=0, wait_cycles=0, host_cycles=0;
    uint32_t word=0;
    unsigned bits=0;
    bool finished=false;
    for (uint64_t cycle=0; cycle<200000000; ++cycle) {
        dut.clk=0; dut.resetn=cycle>=8; dut.eval();
        // The only data crossing the package boundary is this result stream.
        if (dut.resetn && dut.report_strobe) {
            word |= uint32_t(dut.report_bit) << bits;
            if (++bits == 32) { words.push_back(word); bits=0; word=0; }
        }
        if (dut.resetn) {
            valid_cycles += dut.rootp->soc_top__DOT__pcpi_valid;
            wait_cycles += dut.rootp->soc_top__DOT__pcpi_valid && dut.rootp->soc_top__DOT__pcpi_wait;
            accepted += dut.rootp->soc_top__DOT__pcpi_valid && dut.rootp->soc_top__DOT__pcpi_ready;
        }
        dut.clk=1; dut.eval(); ++host_cycles;
        if (dut.resetn && dut.trap && !dut.done) {
            std::fprintf(stderr,"processor trap after %llu cycles\n", (unsigned long long)host_cycles); return 6;
        }
        if (dut.done && !dut.report_strobe) { finished=true; break; }
    }
    uint32_t status=finished && dut.passed && !dut.fault ? 0x600d600d : 0;
    std::printf("{\"status\":%u,\"host_cycles\":%llu,\"pcpi_handshakes\":%llu,"
                "\"pcpi_valid_cycles\":%llu,\"pcpi_wait_cycles\":%llu,"
                "\"fault\":%u,\"partial_report_bits\":%u,\"words\":[",
                status,(unsigned long long)host_cycles,(unsigned long long)accepted,
                (unsigned long long)valid_cycles,(unsigned long long)wait_cycles,
                dut.fault,bits);
    for (size_t j=0;j<words.size();j++) std::printf("%s%u",j ? ",":"",words[j]);
    std::printf("]}\n");
    return status==0x600d600d && bits==0 ? 0 : 7;
}

#include "Vcore_top.h"
#include "verilated.h"
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <iterator>
#include <vector>
int main(int argc, char **argv) {
    Verilated::commandArgs(argc, argv);
    if (argc != 2) return 2;
    std::ifstream file(argv[1], std::ios::binary);
    std::vector<uint8_t> image((std::istreambuf_iterator<char>(file)), {});
    if (!file || image.size() > 65536) return 3;
    std::vector<uint8_t> ram(65536, 0);
    std::copy(image.begin(), image.end(), ram.begin());
    Vcore_top dut;
    std::vector<uint32_t> words;
    uint64_t accepted=0, valid_cycles=0, wait_cycles=0, host_cycles=0;
    uint32_t status=0;
    for (uint64_t cycle=0; cycle<200000000 && !status; ++cycle) {
        dut.clk=0; dut.resetn=cycle>=8;
        dut.mem_ready=1; dut.mem_rdata=0; dut.eval();
        uint32_t addr=dut.mem_addr & ~3u;
        if (addr < ram.size()) {
            for (unsigned j=0;j<4;j++) dut.mem_rdata |= uint32_t(ram[addr+j]) << (8*j);
        }
        dut.eval();
        // All transfers and PCPI handshakes sampled once at the rising edge.
        if (dut.resetn && dut.mem_valid && dut.mem_ready) {
            if (dut.mem_wstrb) {
                if (addr == 0x10000000 && dut.mem_wstrb == 15) words.push_back(dut.mem_wdata);
                else if (addr == 0x10000004 && dut.mem_wstrb == 15) status=dut.mem_wdata;
                else if (addr < ram.size()) {
                    for (unsigned j=0;j<4;j++) if (dut.mem_wstrb & (1<<j)) ram[addr+j]=dut.mem_wdata>>(8*j);
                } else { std::fprintf(stderr,"invalid store at %08x\n",addr); return 4; }
            } else if (addr >= ram.size()) { std::fprintf(stderr,"invalid load at %08x\n",addr); return 5; }
        }
        if (dut.resetn) {
            valid_cycles += dut.debug_pcpi_valid;
            wait_cycles += dut.debug_pcpi_valid && dut.debug_pcpi_wait;
            accepted += dut.debug_pcpi_valid && dut.debug_pcpi_ready;
        }
        dut.clk=1; dut.eval(); ++host_cycles;
        if (dut.resetn && dut.trap && !status) {
            std::fprintf(stderr,"processor trap after %llu cycles\n", (unsigned long long)host_cycles); return 6;
        }
    }
    std::printf("{\"status\":%u,\"host_cycles\":%llu,\"pcpi_handshakes\":%llu,"
                "\"pcpi_valid_cycles\":%llu,\"pcpi_wait_cycles\":%llu,\"words\":[",
                status,(unsigned long long)host_cycles,(unsigned long long)accepted,
                (unsigned long long)valid_cycles,(unsigned long long)wait_cycles);
    for (size_t j=0;j<words.size();j++) std::printf("%s%u",j ? ",":"",words[j]);
    std::printf("]}\n");
    return status==0x600d600d ? 0 : 7;
}

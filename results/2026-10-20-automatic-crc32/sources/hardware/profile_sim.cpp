// Read-only observation of the pinned PicoRV32 instruction counter and PC.
// Counter increments are sampled after the rising edge: reg_pc is then the
// address of the launched instruction. The two rdinstret markers define the
// same measured window as the firmware. Counts must reconcile independently.
#include "Vsoc_top.h"
#include "Vsoc_top___024root.h"
#include "verilated.h"
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <map>
#include <set>
#include <vector>
int main(int argc, char **argv) {
    Verilated::commandArgs(argc, argv);
    if (argc != 2) return 2;
    std::ifstream input(argv[1], std::ios::binary);
    std::vector<uint8_t> binary((std::istreambuf_iterator<char>(input)), {});
    if (binary.empty()) return 2;
    Vsoc_top dut;
    std::vector<uint32_t> words;
    std::map<uint32_t,uint64_t> region, total;
    std::set<uint32_t> starts;
    uint64_t accepted=0, valid_cycles=0, wait_cycles=0, host_cycles=0, previous_count=0;
    uint32_t word=0, previous_pc=0;
    unsigned bits=0, markers=0;
    bool finished=false, have_previous=false;
    for (uint64_t cycle=0; cycle<200000000; ++cycle) {
        dut.clk=0; dut.resetn=cycle>=8; dut.eval();
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
        uint64_t count=dut.rootp->soc_top__DOT__cpu__DOT__count_instr;
        if (dut.resetn && count != previous_count) {
            if (count != previous_count + 1) return 8;
            uint32_t pc=dut.rootp->soc_top__DOT__cpu__DOT__reg_pc;
            if (pc % 4 || pc + 4 > binary.size()) return 9;
            uint32_t opcode=uint32_t(binary[pc]) | uint32_t(binary[pc+1])<<8 |
                            uint32_t(binary[pc+2])<<16 | uint32_t(binary[pc+3])<<24;
            ++total[pc];
            if ((opcode & 0xfffff07f) == 0xc0202073) {
                ++markers;
                if (markers==2 && have_previous) starts.insert(previous_pc+4);
            } else if (markers==1) {
                ++region[pc];
                if (!have_previous || pc!=previous_pc+4) starts.insert(pc);
                previous_pc=pc; have_previous=true;
            }
        }
        previous_count=count;
        if (dut.resetn && dut.trap && !dut.done) return 6;
        if (dut.done && !dut.report_strobe) { finished=true; break; }
    }
    uint32_t status=finished && dut.passed && !dut.fault ? 0x600d600d : 0;
    std::printf("{\"status\":%u,\"host_cycles\":%llu,\"pcpi_handshakes\":%llu,"
                "\"pcpi_valid_cycles\":%llu,\"pcpi_wait_cycles\":%llu,\"markers\":%u,"
                "\"fault\":%u,\"partial_report_bits\":%u,\"words\":[",
                status,(unsigned long long)host_cycles,(unsigned long long)accepted,
                (unsigned long long)valid_cycles,(unsigned long long)wait_cycles,markers,dut.fault,bits);
    for (size_t j=0;j<words.size();j++) std::printf("%s%u",j ? ",":"",words[j]);
    std::printf("],\"region_counts\":{"); bool first=true;
    for (auto item:region) { std::printf("%s\"%u\":%llu",first?"":",",item.first,(unsigned long long)item.second); first=false; }
    std::printf("},\"total_counts\":{"); first=true;
    for (auto item:total) { std::printf("%s\"%u\":%llu",first?"":",",item.first,(unsigned long long)item.second); first=false; }
    std::printf("},\"block_starts\":["); first=true;
    for (auto pc:starts) { std::printf("%s%u",first?"":",",pc); first=false; }
    std::printf("]}\n");
    return status==0x600d600d && bits==0 && markers==2 ? 0 : 7;
}

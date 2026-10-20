// Calibration only: launch-to-launch instruction spans in the pinned SoC.
// Observation comments expose existing registers; they do not change hardware.
#include "Vsoc_top.h"
#include "Vsoc_top___024root.h"
#include "verilated.h"
#include <cstdint>
#include <cstdio>
#include <map>
#include <vector>
struct Span { uint64_t count=0, cycles=0, minimum=UINT64_MAX, maximum=0; };
int main(int argc, char **argv) {
    Verilated::commandArgs(argc, argv);
    Vsoc_top dut;
    std::map<uint32_t, Span> spans;
    uint64_t previous_count=0, previous_cycle=0, handshakes=0, waits=0, valids=0;
    uint32_t previous_pc=0, word=0;
    unsigned bits=0;
    std::vector<uint32_t> words;
    bool have_previous=false, finished=false, trapped=false;
    for (uint64_t cycle=0; cycle<100000; ++cycle) {
        dut.clk=0; dut.resetn=cycle>=8; dut.eval();
        if (dut.resetn && dut.report_strobe) {
            word |= uint32_t(dut.report_bit) << bits;
            if (++bits==32) { words.push_back(word); bits=0; word=0; }
        }
        if (dut.resetn) {
            valids += dut.rootp->soc_top__DOT__pcpi_valid;
            waits += dut.rootp->soc_top__DOT__pcpi_valid && dut.rootp->soc_top__DOT__pcpi_wait;
            handshakes += dut.rootp->soc_top__DOT__pcpi_valid && dut.rootp->soc_top__DOT__pcpi_ready;
        }
        dut.clk=1; dut.eval();
        uint64_t count=dut.rootp->soc_top__DOT__cpu__DOT__count_instr;
        if (dut.resetn && count != previous_count) {
            if (count != previous_count+1) return 8;
            if (have_previous) {
                auto &s=spans[previous_pc];
                uint64_t elapsed=cycle-previous_cycle;
                ++s.count; s.cycles+=elapsed;
                if (elapsed<s.minimum) s.minimum=elapsed;
                if (elapsed>s.maximum) s.maximum=elapsed;
            }
            previous_pc=dut.rootp->soc_top__DOT__cpu__DOT__reg_pc;
            previous_cycle=cycle; have_previous=true;
        }
        previous_count=count;
        if (dut.resetn && dut.trap && !dut.done) { trapped=true; break; }
        if (dut.done && !dut.report_strobe) { finished=true; break; }
    }
    bool passed=finished && dut.passed && !dut.fault && !bits;
    std::printf("{\"passed\":%s,\"trapped\":%s,\"last_pc\":%u,\"handshakes\":%llu,\"wait_cycles\":%llu,\"valid_cycles\":%llu,\"words\":[",
                passed?"true":"false",trapped?"true":"false",previous_pc,
                (unsigned long long)handshakes,(unsigned long long)waits,(unsigned long long)valids);
    for (size_t i=0;i<words.size();++i) std::printf("%s%u",i?",":"",words[i]);
    std::printf("],\"spans\":{"); bool first=true;
    for (const auto &entry:spans) {
        const auto &s=entry.second;
        std::printf("%s\"%u\":{\"count\":%llu,\"cycles\":%llu,\"min\":%llu,\"max\":%llu}",first?"":",",entry.first,
                    (unsigned long long)s.count,(unsigned long long)s.cycles,
                    (unsigned long long)s.minimum,(unsigned long long)s.maximum);
        first=false;
    }
    std::printf("}}\n");
    return passed ? 0 : trapped ? 6 : 7;
}

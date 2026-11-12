// Runs one flat program image on core_top with zero-wait RAM at 0x80000000.
// Adapted from the ML branch's hardware/core_sim.cpp: the program ends by storing
// to tohost like it does on Spike, and the cycles between the stores to
// instret_start and instret_stop give the same window that Spike's trace covers.
#include "Vcore_top.h"
#include "verilated.h"
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <vector>

static const uint32_t RAM_BASE = 0x80000000u, RAM_SIZE = 16u << 20;

int main(int argc, char **argv) {
    if (argc != 6) {
        std::fprintf(stderr, "usage: %s image.bin tohost instret_start instret_stop max_cycles\n", argv[0]);
        return 2;
    }
    uint32_t tohost = std::strtoul(argv[2], 0, 0);
    uint32_t start_addr = std::strtoul(argv[3], 0, 0), stop_addr = std::strtoul(argv[4], 0, 0);
    uint64_t max_cycles = std::strtoull(argv[5], 0, 0);
    std::ifstream file(argv[1], std::ios::binary);
    std::vector<uint8_t> image((std::istreambuf_iterator<char>(file)), {});
    if (!file || image.size() > RAM_SIZE) return 3;
    std::vector<uint8_t> ram(RAM_SIZE, 0);
    std::copy(image.begin(), image.end(), ram.begin());

    Vcore_top dut;
    uint64_t cycle = 0, start_cycle = 0, stop_cycle = 0;
    uint32_t exit_word = 0;
    bool done = false;
    const char *error = 0;
    for (; cycle < max_cycles && !done && !error; ++cycle) {
        dut.clk = 0; dut.resetn = cycle >= 8;
        dut.mem_ready = 1; dut.mem_rdata = 0; dut.eval();
        uint32_t offset = (dut.mem_addr & ~3u) - RAM_BASE;
        bool in_ram = offset < RAM_SIZE;
        if (in_ram)
            for (unsigned j = 0; j < 4; j++) dut.mem_rdata |= uint32_t(ram[offset + j]) << (8 * j);
        dut.eval();
        // every transfer is sampled once at the rising edge
        if (dut.resetn && dut.mem_valid && dut.mem_ready) {
            if (!in_ram) error = dut.mem_wstrb ? "store outside RAM" : "load outside RAM";
            else if (dut.mem_wstrb) {
                for (unsigned j = 0; j < 4; j++)
                    if (dut.mem_wstrb & (1 << j)) ram[offset + j] = dut.mem_wdata >> (8 * j);
                uint32_t addr = dut.mem_addr & ~3u;
                if (addr == start_addr) start_cycle = cycle;
                if (addr == stop_addr) stop_cycle = cycle;
                if (addr == tohost) { exit_word = dut.mem_wdata; done = true; }
            }
        }
        dut.clk = 1; dut.eval();
        if (dut.resetn && dut.trap && !done) error = "processor trap";
    }
    if (!done && !error) error = "cycle limit reached";

    auto word = [&](uint32_t addr) {
        uint32_t o = addr - RAM_BASE, v = 0;
        for (unsigned j = 0; j < 4; j++) v |= uint32_t(ram[o + j]) << (8 * j);
        return v;
    };
    // the hooks store the core's own rdinstret values at the window edges
    uint32_t instret = word(stop_addr) - word(start_addr);
    std::printf("{\"error\":%s%s%s,\"exit_word\":%u,\"total_cycles\":%llu,"
                "\"window_cycles\":%llu,\"instret\":%u}\n",
                error ? "\"" : "", error ? error : "null", error ? "\"" : "", exit_word,
                (unsigned long long)cycle, (unsigned long long)(stop_cycle - start_cycle), instret);
    // startup.S writes (main's return value << 1) | 1, so 1 means the benchmark verified
    return !error && exit_word == 1 ? 0 : 1;
}

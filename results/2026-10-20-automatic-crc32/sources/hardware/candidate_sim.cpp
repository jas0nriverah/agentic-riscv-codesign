#include "Vcandidate.h"
#include "verilated.h"
#include <cstdint>
#include <cstdio>
#include <fstream>
int main(int argc, char **argv) {
    if (argc != 2) return 2;
    Vcandidate dut;
    std::ifstream input(argv[1]);
    uint32_t a, b, expected;
    unsigned count = 0;
    while (input >> a >> b >> expected) {
        dut.in0 = a; dut.in1 = b; dut.eval();
        if (dut.result != expected) {
            std::fprintf(stderr, "mismatch: %u %u expected=%u actual=%u\n", a,b,expected,dut.result);
            return 3;
        }
        ++count;
    }
    if (!input.eof() || count != 228) return 4;
    std::printf("independent RV32 oracle: %u comparisons passed\n", count);
    return 0;
}

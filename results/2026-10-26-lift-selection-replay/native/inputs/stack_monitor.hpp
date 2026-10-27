#ifndef ISAFORGE_STACK_MONITOR_HPP
#define ISAFORGE_STACK_MONITOR_HPP
#include <cstdint>
// Passive simulator checks. No state is written back into the processor.
struct StackMonitor {
    uint32_t program_end, writable_start, floor;
    bool initialized=false;
    uint32_t min_sp=8192;
    uint64_t checked_cycles=0, violations=0;
    uint32_t first_pc=0, first_address=0;
    const char *first_kind="none";
    StackMonitor(uint32_t end, uint32_t writable, uint32_t stack_floor)
        : program_end(end), writable_start(writable), floor(stack_floor) {}
    bool valid_configuration() const {
        return floor==6528 && writable_start<=program_end && program_end<=6400;
    }
    void violation(const char *kind, uint32_t pc, uint32_t address) {
        if (!violations) { first_kind=kind; first_pc=pc; first_address=address; }
        ++violations;
    }
    void observe_sp(uint32_t sp, uint32_t pc) {
        if (!initialized) { if (sp!=8192) return; initialized=true; }
        ++checked_cycles;
        if (sp<min_sp) min_sp=sp;
        if (sp<floor || sp>8192) violation("stack-pointer",pc,sp);
    }
    void observe_write(uint32_t address, uint8_t strobes, uint32_t pc) {
        // RAM strobes select bytes in the aligned bus word, not addr+lane.
        if (address>=8192) return;
        uint32_t base=address & ~uint32_t(3);
        for (unsigned lane=0; lane<4; ++lane) {
            if (!(strobes & (1u<<lane))) continue;
            uint32_t byte=base+lane;
            if (!((writable_start<=byte && byte<program_end) || (floor<=byte && byte<8192)))
                violation("ram-write",pc,byte);
        }
    }
    uint32_t max_stack_bytes() const { return min_sp<=8192 ? 8192-min_sp : 0; }
};
#endif

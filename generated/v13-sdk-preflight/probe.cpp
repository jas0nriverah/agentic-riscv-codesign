#include <cstdint>
#include <vector>
int main() { std::vector<std::uint32_t> v{1, 2}; return v[0] + v[1] == 3 ? 0 : 1; }

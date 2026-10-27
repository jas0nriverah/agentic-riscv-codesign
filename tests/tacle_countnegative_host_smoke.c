extern void initialise_benchmark(void);
extern int benchmark(void);
extern int verify_benchmark(int);

int main(void) {
    initialise_benchmark();
    int result = benchmark();
    return verify_benchmark(result) ? 0 : 1;
}

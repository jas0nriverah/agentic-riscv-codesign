/* Upstream included unchanged to inspect its file-local buffer. */
#define main tacle_original_main
#include "/Users/jasonrivera/Documents/Codex/2026-10-11/can-this-run-offline/work/agentic-riscv-codesign/generated/external-v5/cohort-02/sources/bench/sequential/anagram/anagram.c"
#undef main
#include <stdint.h>
unsigned external_snapshot(int32_t *values) {
    for(unsigned i=0;i<30;i++) values[i]=(unsigned char)anagram_buffer[i];
    return 30;
}
/* Correctness-only single-phrase probe, never a scored/traced workload variant. */
void external_anagram_phrase(unsigned i) {
    anagram_Reset(); anagram_BuildMask(anagram_achPhrase[i]); anagram_AddWords();
    if(anagram_cpwCand && anagram_cchPhraseLength) {
        anagram_cpwLast=0; anagram_SortCandidates();
        anagram_FindAnagram(anagram_aqMainMask,anagram_apwCand,0);
    }
}

"""Compare the freestanding runtime with the host C library in C locale."""
from pathlib import Path
import shutil
import subprocess

import pytest


def test_c_locale_character_classes_and_string_edge_cases(tmp_path):
    cc = shutil.which('cc')
    if not cc:
        pytest.skip('Host C compiler unavailable')
    source = Path(__file__).resolve().parents[1] / 'hardware/embench_strings.c'
    obj = tmp_path / 'strings.o'
    subprocess.run([cc, '-std=c11', '-fno-builtin', '-Dstrlen=isaforge_strlen', '-Dstrchr=isaforge_strchr',
                    '-c', str(source), '-o', str(obj)], check=True, capture_output=True)
    check = tmp_path / 'check.c'
    check.write_text(r'''
#include <ctype.h>
#include <locale.h>
#include <stddef.h>
#include <string.h>
extern const char _ctype_[257];
size_t isaforge_strlen(const char *);
char *isaforge_strchr(const char *, int);
int main(void) {
    if (!setlocale(LC_CTYPE, "C")) return 1;
    for (int i=-1;i<=255;++i) {
        unsigned char flags=(unsigned char)_ctype_[i+1];
        if (!!(flags&3)!=!!isalpha(i) || !!(flags&4)!=!!isdigit(i) ||
            !!(flags&8)!=!!isspace(i) || !!(flags&16)!=!!ispunct(i) ||
            !!(flags&32)!=!!iscntrl(i) || !!(flags&68)!=!!isxdigit(i) ||
            !!(flags&151)!=!!isprint(i)) return 2;
    }
    const char data[]={'a','b','a',(char)255,0,'x',0};
    for (size_t offset=0;offset<sizeof(data);++offset) {
        if (isaforge_strlen(data+offset)!=strlen(data+offset)) return 3;
        for (int c=-1;c<=256;++c)
            if (isaforge_strchr(data+offset,c)!=strchr(data+offset,c)) return 4;
    }
    return 0;
}
''')
    executable = tmp_path / 'check'
    subprocess.run([cc, '-std=c11', '-fno-builtin', str(check), str(obj), '-o', str(executable)],
                   check=True, capture_output=True)
    subprocess.run([str(executable)], check=True, capture_output=True)

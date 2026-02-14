from setuptools import setup, Extension
from Cython.Build import cythonize

extensions = [
    Extension("memory", ["memory.pyx"]),
    Extension("ppu", ["ppu.pyx"]),
    Extension("apu", ["apu.pyx"]),
    Extension("cpu", ["cpu.pyx"]),
    Extension("nes_loop", ["nes_loop.pyx"]),
]

setup(
    ext_modules=cythonize(extensions, compiler_directives={
        "boundscheck": False,
        "wraparound": False,
        "cdivision": True,
        "language_level": 3,
    }),
)

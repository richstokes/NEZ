from setuptools import setup, Extension
from Cython.Build import cythonize

extensions = [
    Extension("ppu", ["ppu.pyx"]),
]

setup(
    ext_modules=cythonize(extensions, compiler_directives={
        "boundscheck": False,
        "wraparound": False,
        "cdivision": True,
        "language_level": 3,
    }),
)

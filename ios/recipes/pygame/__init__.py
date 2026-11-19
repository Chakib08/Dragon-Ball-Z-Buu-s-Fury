"""kivy-ios recipe for pygame (kivy-ios has none).

    copied into kivy-ios's recipes folder (kivy_ios/recipes/pygame), then
    toolchain build python3 pygame

(As a kivy-ios recipe of its own: `toolchain create` only links the
libraries of those, not of recipes given with --add-custom-recipe.)

Built like kivy-ios builds Pillow: pygame's own setup.py compiles its C
modules (one per file, as on Android), kivy-ios's liblink turns each into
an object file and biglink gathers them into libpygame.a, linked into the
app. The pygame source on PyPI already holds the C files Cython makes, so no
Cython runs.

Two things differ from a desktop build:

- iOS apps cannot load native code at run time: every module is linked into
  the app, and kivy-ios's importer finds "pygame.base" by looking up the C
  function PyInit_pygame_base. pygame names them PyInit_base, PyInit_math...,
  and PyInit_math and PyInit_time already exist in Python itself (its math
  and time modules). So pygame's MODINIT_DEFINE macro is changed to name
  them PyInit_pygame_<module>.
- The modules are those of pygame's Android build (buildconfig/
  Setup.Android.SDL2.in) without the optional ones the game does not use and
  that this naming does not fit: pygame._sdl2.* (their names are in a
  sub-package), _sprite and scrap (the clipboard). pygame imports them only
  if they are there.
"""

from os.path import join

import sh

from kivy_ios.toolchain import CythonRecipe, shprint

# Lines of the Android module list left out on iOS (see above)
EXCLUDED_MODULES = ("_sdl2.", "_sprite ", "scrap ", "pypm ")


class PygameRecipe(CythonRecipe):
    version = "2.6.1"
    url = "https://files.pythonhosted.org/packages/source/p/pygame/pygame-{version}.tar.gz"
    library = "libpygame.a"
    depends = ["hostpython3", "python3", "ios", "sdl2", "sdl2_image", "sdl2_ttf", "sdl2_mixer"]
    python_depends = ["setuptools"]
    # The iOS frameworks SDL needs come with kivy-ios's sdl2 recipes
    cythonize = False  # the C files are in the source already

    def prebuild_platform(self, plat):
        if self.has_marker("patched"):
            return
        self.rename_module_init_functions()
        self.write_setup_file()
        self.set_marker("patched")

    def rename_module_init_functions(self):
        """PyInit_<module> -> PyInit_pygame_<module> (see the top)."""
        path = join(self.build_dir, "src_c", "pgcompat.h")
        with open(path) as file:
            source = file.read()
        original = "#define MODINIT_DEFINE(mod_name) PyMODINIT_FUNC PyInit_##mod_name(void)"
        if original not in source:
            raise RuntimeError("pygame's pgcompat.h changed: update the iOS recipe")
        source = source.replace(
            original, "#define MODINIT_DEFINE(mod_name) PyMODINIT_FUNC PyInit_pygame_##mod_name(void)")
        with open(path, "w") as file:
            file.write(source)

    def write_setup_file(self):
        """pygame's module list ("Setup"), from its Android one, with
        kivy-ios's SDL2 headers."""
        with open(join(self.build_dir, "buildconfig", "Setup.Android.SDL2.in")) as file:
            template = file.read()
        include = join(self.ctx.dist_dir, "include", "common")
        setup = template.format(
            sdl_includes="-I" + join(include, "sdl2"),
            sdl_ttf_includes="-I" + join(include, "sdl2_ttf"),
            sdl_image_includes="-I" + join(include, "sdl2_image"),
            sdl_mixer_includes="-I" + join(include, "sdl2_mixer"),
            jpeg_includes="",
            png_includes="",
            freetype_includes="",
        )
        lines = [line for line in setup.splitlines()
                 if not line.lstrip().startswith(EXCLUDED_MODULES)]
        with open(join(self.build_dir, "Setup"), "w") as file:
            file.write("\n".join(lines) + "\n")

    def get_recipe_env(self, plat):
        env = super().get_recipe_env(plat)
        env["CFLAGS"] = env.get("CFLAGS", "") + " -I" + join(plat.sysroot, "usr", "include")
        # pygame's setup.py then leaves the docs and tests out (as for Android)
        env["PYGAME_ANDROID"] = "TRUE"
        env["PYGAME_CROSS_COMPILE"] = "TRUE"
        return env

    def build_platform(self, plat):
        build_env = self.get_recipe_env(plat)
        hostpython = sh.Command(self.ctx.hostpython)
        shprint(hostpython, "setup.py", "build_ext", "-g", _env=build_env)
        self.biglink()

    def reduce_python_package(self):
        import shutil
        destination = join(self.ctx.site_packages_dir, "pygame")
        for folder in ("tests", "examples", "docs"):
            shutil.rmtree(join(destination, folder), ignore_errors=True)


recipe = PygameRecipe()

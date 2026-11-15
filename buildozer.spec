[app]

title = Dragon Ball Z Buu's Fury
package.name = dragonballzbuusfury
package.domain = org.chakib08
source.dir = .
source.include_exts = py,png,jpg,ttf,tmx,tsx,json,yaml,wav
source.exclude_dirs = .git,.github,.buildozer,bin,__pycache__
version = 0.1.0
requirements = python3,pygame,pytmx,pyscroll,pyyaml
orientation = landscape
fullscreen = 1

android.api = 35
android.minapi = 21
android.ndk = 28c
android.archs = arm64-v8a,armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = False

[buildozer]
log_level = 2
warn_on_root = 1

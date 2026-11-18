[app]

title = Dragon Ball Z Buus Fury
package.name = dragonballzbuusfury
package.domain = org.chakib08
source.dir = .
source.include_exts = py,png,jpg,ttf,tmx,tsx,json,wav
source.exclude_dirs = .git,.github,.buildozer,.p4a,bin,__pycache__,.venv,server,tools,tests,rips
# The full-size icon picture (the launcher uses Graphics/android/icon.png)
source.exclude_patterns = Graphics/android_icon.png
version = 0.1.0
requirements = python3,pygame,pytmx==3.32,pyscroll==2.31
orientation = landscape
fullscreen = 1
# Launcher icon: made from Graphics/android_icon.png by tools/make_android_icon.py
icon.filename = %(source.dir)s/Graphics/android/icon.png
# Online 1v1 connects to the lobby server
android.permissions = INTERNET

android.api = 35
android.minapi = 21
android.ndk = 28c
android.archs = arm64-v8a,armeabi-v7a
android.accept_sdk_license = True
android.allow_backup = False

p4a.source_dir = .p4a

[buildozer]
log_level = 2
warn_on_root = 1

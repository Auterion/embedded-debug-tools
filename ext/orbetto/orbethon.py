import os 

os.system('meson setup build')
os.system('ninja -C build')

from build.orbethon import *
import sys
from shlex import split
orbethon(len(sys.argv),sys.argv)
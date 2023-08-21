# -*- mode: python ; coding: utf-8 -*-

import gooey
import os

gooey_root = os.path.dirname(gooey.__file__)
root = os.getcwd()
# Path to delta.json
gooey_languages = Tree(f'{root}/languages' , prefix='/languages')

block_cipher = None

a = Analysis(['app.py'],  
             pathex=[root], # path
             binaries=[],
             datas=[],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          [('u', None, 'OPTION')],
          gooey_languages,
          name='DeltaCommandApp',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          upx_exclude=[],
          runtime_tmpdir=None,
          console=False,
          icon=os.path.join(gooey_root, 'images', 'program_icon.ico'))
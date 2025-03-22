@echo off

:: Activate the conda environment
call conda activate etvr

:: Remove build and dist directories (with confirmation)
if exist build (
    rmdir /s build
)
if exist dist (
    rmdir /s dist
)

:: Run PyInstaller with the specified spec file
pyinstaller .\babbleapp.spec

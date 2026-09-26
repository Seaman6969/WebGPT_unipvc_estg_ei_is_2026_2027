#!/bin/bash
set -e

cd "$(dirname "$0")"

APP_NAME="WebGPT"
BIN_NAME="webgpt"
OUTPUT="${APP_NAME}-x86_64.AppImage"

echo ">>> Sourcing virtual environment"
source v/bin/activate

export PYTHONDONTWRITEBYTECODE=1

echo ">>> Ensuring pyproject.toml"
if [ ! -f "pyproject.toml" ]; then
    cat > pyproject.toml << 'EOF'
[project]
name = "WebGPT"
version = "1"
description = "WebGPT intelligent procurement and data assistant backend"
requires-python = ">=3.10"
dependencies = [
    "fastapi",
    "uvicorn",
    "chromadb",
    "requests",
    "pypdf",
    "openpyxl",
    "pandas",
    "python-docx",
    "ollama",
    "scipy",
]

[project.scripts]
webgpt = "main:main"

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools]
py-modules = ["main", "server"]
packages = [
    "attachments",
    "chat",
    "config",
    "local",
    "ollama",
    "rag",
    "utils",
]
EOF
fi

echo ">>> Cleaning previous build artifacts"
rm -rf build dist "${APP_NAME}.AppDir" "${OUTPUT}"

if [ ! -x "./appimagetool" ]; then
    if [ -f "../LocalGPT/appimagetool" ]; then
        cp ../LocalGPT/appimagetool ./appimagetool
    elif [ -f "../PrivateGPT/appimagetool" ]; then
        cp ../PrivateGPT/appimagetool ./appimagetool
    elif [ -f "../appimagetool" ]; then
        cp ../appimagetool ./appimagetool
    fi
    chmod +x ./appimagetool 2>/dev/null || true
fi

echo ">>> Building binary with PyInstaller"
python -B -m PyInstaller --clean --noconfirm webgpt.spec

echo ">>> Assembling AppDir"
mkdir -p "${APP_NAME}.AppDir/usr/bin"
mkdir -p "${APP_NAME}.AppDir/usr/share/icons/hicolor/256x256/apps"
cp -a dist/${BIN_NAME}/* "${APP_NAME}.AppDir/usr/bin/"

if [ -d "static" ]; then
    cp -r static "${APP_NAME}.AppDir/usr/bin/static"
fi

if [ -f "assets/icon.png" ]; then
    cp assets/icon.png "${APP_NAME}.AppDir/${APP_NAME}.png"
    cp assets/icon.png "${APP_NAME}.AppDir/usr/share/icons/hicolor/256x256/apps/${APP_NAME}.png"
fi

cat > "${APP_NAME}.AppDir/${APP_NAME}.desktop" << EOF
[Desktop Entry]
Name=${APP_NAME}
Comment=Intelligent AI Procurement & Data Assistant
Exec=${BIN_NAME}
Icon=${APP_NAME}
Type=Application
Categories=Utility;Network;
Terminal=false
EOF

cat > "${APP_NAME}.AppDir/AppRun" << EOF
#!/bin/sh
export PYTHONDONTWRITEBYTECODE=1
HERE="\$(dirname "\$(readlink -f "\${0}")")"
exec "\${HERE}/usr/bin/${BIN_NAME}" "\$@"
EOF

chmod +x "${APP_NAME}.AppDir/AppRun"
chmod +x "${APP_NAME}.AppDir/usr/bin/${BIN_NAME}"

echo ">>> Generating AppImage"
ARCH=x86_64 ./appimagetool --appimage-extract-and-run "${APP_NAME}.AppDir" "${OUTPUT}"

echo ">>> Cleaning temporary bytecode if any"
find . -not -path "./v*" -not -path "./${APP_NAME}.AppDir*" -not -path "./dist*" -not -path "./build*" \( -name "*pycache*" -o -name "*.pyc" -o -name "*.pyo" \) -delete 2>/dev/null || true
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -name "*.pyc" -delete 2>/dev/null || true

echo
echo ">>> Build complete: $(pwd)/${OUTPUT}"

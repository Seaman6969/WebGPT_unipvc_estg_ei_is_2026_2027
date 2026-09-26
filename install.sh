#!/usr/bin/env bash
set -euo pipefail

REPO="Seaman6969/WebGPT_unipvc_estg_ei_is_2026_2027"
BRANCH="main"
APP_NAME="WebGPT"
BINARY_NAME="WebGPT-x86_64.AppImage"
INSTALL_DIR="${HOME}/.local/bin"
DATA_DIR="${HOME}/.local/share/WebGPT"
STATIC_DIR="${DATA_DIR}/static"
VERSION="${WEBGPT_VERSION:-latest}"

info()  { printf '\033[1;34m[info]\033[0m  %s\n' "$*"; }
warn()  { printf '\033[1;33m[warn]\033[0m  %s\n' "$*" >&2; }
error() { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

# --- platform check ----------------------------------------------------------
[ "$(uname -s)" = "Linux" ] || error "This installer targets Linux."
[ "$(uname -m)" = "x86_64" ] || error "Only x86_64 is supported (got: $(uname -m))."

command -v curl >/dev/null 2>&1 || error "curl is required."
command -v tar  >/dev/null 2>&1 || error "tar is required."

# --- resolve URLs ------------------------------------------------------------
if [ "$VERSION" = "latest" ]; then
    APPIMAGE_URL="https://github.com/${REPO}/releases/latest/download/${BINARY_NAME}"
    TARBALL_URL="https://github.com/${REPO}/archive/refs/heads/${BRANCH}.tar.gz"
else
    APPIMAGE_URL="https://github.com/${REPO}/releases/download/${VERSION}/${BINARY_NAME}"
    TARBALL_URL="https://github.com/${REPO}/archive/refs/tags/${VERSION}.tar.gz"
fi

# --- workspace ---------------------------------------------------------------
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$INSTALL_DIR" "$DATA_DIR"
TARGET="${INSTALL_DIR}/${BINARY_NAME}"

# --- download AppImage -------------------------------------------------------
info "Downloading ${APP_NAME}..."
curl -fL --progress-bar -o "${TARGET}.tmp" "$APPIMAGE_URL" \
    || error "Download failed: ${APPIMAGE_URL}"
mv "${TARGET}.tmp" "$TARGET"
chmod +x "$TARGET"

# --- download static assets --------------------------------------------------
info "Downloading static assets..."
curl -fL --progress-bar -o "$TMP/repo.tar.gz" "$TARBALL_URL" \
    || error "Download failed: ${TARBALL_URL}"

mkdir -p "$TMP/extract"
tar -xzf "$TMP/repo.tar.gz" -C "$TMP/extract"

STATIC_SRC="$(find "$TMP/extract" -maxdepth 2 -type d -name static | head -n1)"
[ -n "$STATIC_SRC" ] || error "static/ folder not found in repo tarball"

rm -rf "$STATIC_DIR"
mv "$STATIC_SRC" "$STATIC_DIR"
info "Static assets installed to ${STATIC_DIR}"

# --- PATH (only if needed) ---------------------------------------------------
if ! case ":${PATH}:" in *:"${INSTALL_DIR}":*) true;; *) false;; esac; then
    for rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
        [ -f "$rc" ] || continue
        grep -q "${INSTALL_DIR}" "$rc" || \
            echo "export PATH=\"${INSTALL_DIR}:\$PATH\"" >> "$rc"
    done
fi

# --- FUSE check --------------------------------------------------------------
RUN_FLAGS=()
if ! ldconfig -p 2>/dev/null | grep -q 'libfuse\.so\.2'; then
    warn "libfuse2 not detected — falling back to --appimage-extract-and-run."
    RUN_FLAGS=(--appimage-extract-and-run)
fi

# --- launch ------------------------------------------------------------------
# WebGPT needs to know where its static assets live. Adjust the variable
# name below to match what the app actually reads at startup.
export WEBGPT_STATIC_DIR="$STATIC_DIR"

info "Launching ${APP_NAME} (browser will open automatically)..."
exec "$TARGET" "${RUN_FLAGS[@]+"${RUN_FLAGS[@]}"}"
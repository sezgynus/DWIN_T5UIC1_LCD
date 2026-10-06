#!/usr/bin/env bash
set -euo pipefail

APP_NAME="KlipperDWIN"
SERVICE_NAME="KlipperDWIN"
REPO_URL="https://github.com/sezgynus/KlipperDWIN.git"
INSTALL_USER="${SUDO_USER:-$USER}"
INSTALL_HOME="$(getent passwd "$INSTALL_USER" | cut -d: -f6)"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXPECTED_REPO_DIR="$INSTALL_HOME/KlipperDWIN"
VENV_DIR="$INSTALL_HOME/klipperdwin-env"
APP_CONFIG_DIR="$INSTALL_HOME/.config/KlipperDWIN"
ENV_FILE="$APP_CONFIG_DIR/KlipperDWIN.env"

if [[ "$REPO_DIR" != "$EXPECTED_REPO_DIR" ]]; then
    echo "KlipperDWIN must be cloned to $EXPECTED_REPO_DIR" >&2
    exit 1
fi

if [[ ! -d "$REPO_DIR/.git" ]]; then
    echo "$REPO_DIR is not a Git repository." >&2
    exit 1
fi

if [[ -n "$(git -C "$REPO_DIR" status --porcelain)" ]]; then
    echo "The KlipperDWIN repository must be clean before installation." >&2
    exit 1
fi

if [[ -n "${MOONRAKER_CONFIG:-}" ]]; then
    MOONRAKER_CONF="$MOONRAKER_CONFIG"
elif [[ -f "$INSTALL_HOME/printer_data/config/moonraker.conf" ]]; then
    MOONRAKER_CONF="$INSTALL_HOME/printer_data/config/moonraker.conf"
elif [[ -f "$INSTALL_HOME/moonraker.conf" ]]; then
    MOONRAKER_CONF="$INSTALL_HOME/moonraker.conf"
else
    echo "Moonraker configuration not found. Set MOONRAKER_CONFIG=/path/to/moonraker.conf and run again." >&2
    exit 1
fi

MOONRAKER_CONFIG_DIR="$(dirname "$MOONRAKER_CONF")"
if [[ "$(basename "$MOONRAKER_CONFIG_DIR")" == "config" ]]; then
    MOONRAKER_DATA_DIR="$(dirname "$MOONRAKER_CONFIG_DIR")"
else
    MOONRAKER_DATA_DIR="$INSTALL_HOME/printer_data"
fi
UPDATE_CONF="$MOONRAKER_CONFIG_DIR/KlipperDWIN.conf"
ASVC_FILE="$MOONRAKER_DATA_DIR/moonraker.asvc"

echo "Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y git python3-venv python3-dev build-essential

echo "Preparing Python environment..."
if [[ ! -x "$VENV_DIR/bin/python" ]]; then
    sudo -u "$INSTALL_USER" python3 -m venv "$VENV_DIR"
fi
sudo -u "$INSTALL_USER" "$VENV_DIR/bin/python" -m pip install --upgrade pip
sudo -u "$INSTALL_USER" "$VENV_DIR/bin/python" -m pip install -r "$REPO_DIR/requirements.txt"

echo "Preparing KlipperDWIN configuration..."
sudo -u "$INSTALL_USER" mkdir -p "$APP_CONFIG_DIR"
if [[ ! -f "$ENV_FILE" ]]; then
    sed "s|^DWIN_SETTINGS_FILE=.*|DWIN_SETTINGS_FILE=$APP_CONFIG_DIR/presets.json|" \
        "$REPO_DIR/dwin-lcd.env.example" > "$ENV_FILE"
    chown "$INSTALL_USER:$INSTALL_USER" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
fi

supp_groups=()
for group in dialout gpio; do
    if getent group "$group" >/dev/null; then
        sudo usermod -aG "$group" "$INSTALL_USER"
        supp_groups+=("$group")
    fi
done

SUPPLEMENTARY_LINE=""
if (("${#supp_groups[@]}" > 0)); then
    SUPPLEMENTARY_LINE="SupplementaryGroups=${supp_groups[*]}"
fi

echo "Installing systemd service..."
sed \
    -e "s|@KLIPPERDWIN_USER@|$INSTALL_USER|g" \
    -e "s|@KLIPPERDWIN_HOME@|$INSTALL_HOME|g" \
    -e "s|@SUPPLEMENTARY_GROUPS@|$SUPPLEMENTARY_LINE|g" \
    "$REPO_DIR/simpleLCD.service" | sudo tee "/etc/systemd/system/$SERVICE_NAME.service" >/dev/null
sudo systemctl daemon-reload

echo "Registering Moonraker Update Manager..."
cat > "$UPDATE_CONF" <<EOF
[update_manager KlipperDWIN]
type: git_repo
channel: dev
path: ~/KlipperDWIN
origin: $REPO_URL
primary_branch: master
virtualenv: ~/klipperdwin-env
requirements: requirements.txt
managed_services: KlipperDWIN
EOF
chown "$INSTALL_USER:$INSTALL_USER" "$UPDATE_CONF"

INCLUDE_LINE="[include KlipperDWIN.conf]"
if ! grep -Fqx "$INCLUDE_LINE" "$MOONRAKER_CONF"; then
    printf '\n%s\n' "$INCLUDE_LINE" >> "$MOONRAKER_CONF"
fi

mkdir -p "$MOONRAKER_DATA_DIR"
touch "$ASVC_FILE"
if ! grep -Fqx "$SERVICE_NAME" "$ASVC_FILE"; then
    printf '%s\n' "$SERVICE_NAME" >> "$ASVC_FILE"
fi
chown "$INSTALL_USER:$INSTALL_USER" "$ASVC_FILE"

sudo systemctl enable --now "$SERVICE_NAME.service"

if systemctl list-unit-files moonraker.service >/dev/null 2>&1; then
    sudo systemctl restart moonraker.service
else
    echo "Moonraker service name was not detected as moonraker.service."
    echo "Restart your Moonraker instance so it loads KlipperDWIN.conf and moonraker.asvc."
fi

echo
echo "KlipperDWIN installation complete."
echo "Edit: $ENV_FILE"
echo "Service: $SERVICE_NAME.service"
echo "Moonraker updater: [update_manager KlipperDWIN]"

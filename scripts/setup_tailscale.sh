#!/bin/bash
echo "Installing Tailscale..."
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
echo "Tailscale is up."

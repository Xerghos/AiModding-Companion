#!/bin/bash
# Script de démarrage rapide pour capturer les payloads gemini-cli
# Usage: bash scripts/START_CAPTURE.sh

echo "================================================================================"
echo "DEMARRAGE DE LA CAPTURE PAYLOADS GEMINI-CLI"
echo "================================================================================"
echo ""

# Vérifier si mitmproxy est installé
if ! python3 -c "import mitmproxy" 2>/dev/null; then
    echo "[ERREUR] mitmproxy n'est pas installe"
    echo ""
    echo "Installation de mitmproxy..."
    pip install mitmproxy
    if [ $? -ne 0 ]; then
        echo "[ERREUR] Echec de l'installation de mitmproxy"
        exit 1
    fi
fi

echo "[OK] mitmproxy est installe"
echo ""

# Vérifier si le proxy est déjà en cours d'exécution
if pgrep -f "mitmdump" > /dev/null; then
    echo "[WARN] mitmproxy semble deja en cours d'execution"
    echo "       Arretez-le d'abord si vous voulez le redemarrer"
    echo ""
fi

echo "================================================================================"
echo "INSTRUCTIONS"
echo "================================================================================"
echo ""
echo "1. Ce script va demarrer le proxy mitmproxy"
echo "2. Dans un AUTRE terminal, configurez gemini-cli:"
echo "   export HTTP_PROXY=http://localhost:8080"
echo "   export HTTPS_PROXY=http://localhost:8080"
echo "3. Dans le MEME terminal (ou les variables sont definies), executez gemini-cli"
echo "4. Les payloads seront sauvegardes dans logs/"
echo ""
echo "================================================================================"
echo "DEMARRAGE DU PROXY"
echo "================================================================================"
echo ""

# Démarrer mitmproxy
mitmdump -s scripts/capture_gemini_cli_mitmproxy.py

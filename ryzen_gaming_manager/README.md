# Gestionnaire Ryzen AI pour Gaming

Ce package contient des scripts pour optimiser les performances de gaming sur les systèmes Ryzen AI en désactivant temporairement l'environnement AI.

## 📁 Fichiers

- `disable_ryzen_for_gaming.ps1` - Désactive Ryzen AI pour le gaming
- `enable_ryzen_ai.ps1` - Réactive Ryzen AI après gaming
- `gaming_mode.bat` - Lanceur batch pour gaming (admin requis)
- `ai_mode.bat` - Lanceur batch pour AI (admin requis)

## 🎮 Utilisation

### Pour jouer (Mode Gaming) :
1. **Exécutez `gaming_mode.bat` en tant qu'administrateur**
2. Le script va :
   - Retirer Conda du PATH
   - Arrêter les services AMD non essentiels
   - Terminer les processus Ryzen AI
   - Libérer la mémoire

### Pour l'indexation AI (Mode AI) :
1. **Exécutez `ai_mode.bat` en tant qu'administrateur**
2. Le script va :
   - Restaurer Conda dans le PATH
   - Redémarrer les services AMD
   - Vérifier l'environnement Ryzen AI
   - Tester ONNX Runtime

## ⚙️ Ce que font les scripts

### En mode Gaming :
- ✅ Retire Conda/Anaconda du PATH système
- ✅ Arrête les services AMD consommateurs
- ✅ Tue les processus Python/Conda en arrière-plan
- ✅ Désactive les tâches planifiées AMD
- ✅ Nettoie la mémoire

### En mode AI :
- ✅ Restaure Conda dans le PATH
- ✅ Redémarre les services AMD nécessaires
- ✅ Réactive les tâches planifiées
- ✅ Vérifie que l'environnement Ryzen AI fonctionne
- ✅ Teste ONNX Runtime avec VitisAI

## 🔧 Configuration requise

- Windows 10/11 avec PowerShell 5.1+
- Droits administrateur pour modifier le PATH et les services
- Environnement Ryzen AI 1.6.1 installé
- Conda dans le chemin standard (`C:\ProgramData\Anaconda3`)

## ⚠️ Notes importantes

1. **Toujours exécuter en administrateur** pour que les modifications prennent effet
2. **Ne fermez pas la fenêtre** tant que le script n'a pas affiché le message de fin
3. Si vous avez installé Conda ailleurs, modifiez les chemins dans `enable_ryzen_ai.ps1`

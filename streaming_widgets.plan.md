# Guide d'Implémentation : Affichage Streaming des Réponses

Ce document détaille les modifications nécessaires pour activer l'affichage progressif (streaming) des réponses de l'IA dans l'interface utilisateur, remplaçant l'affichage en bloc à la fin.

## 🎯 Objectif
Afficher les tokens (texte et pensées) au fur et à mesure qu'ils arrivent du worker, sans attendre la fin de la génération, pour une expérience utilisateur fluide (2-4s de perception vs 15s+ actuellement).

## 🏗️ Architecture "Stream-to-Buffer -> Finalize-to-Rich"

Le rendu HTML/Markdown temps réel étant coûteux et instable, nous adopterons une approche hybride :
1.  **Phase Streaming :** Le contenu est ajouté brut dans des widgets textes simples (`ThinkingWidget` pour les pensées, `CTkTextbox` pour la réponse).
2.  **Phase Finalisation :** Une fois le stream terminé, le contenu brut est parsé et remplacé par les widgets riches (`MarkdownViewer`, `CodeBox`, etc.).

---

## 📝 Modifications requises dans `ui/widgets.py`

### 1. `ThinkingWidget` : Support de l'ajout progressif
Ajouter une méthode pour insérer du texte sans recharger tout le contenu.

```python
class ThinkingWidget(ctk.CTkFrame):
    # ... existant ...

    def append_text(self, text):
        """Ajoute du texte au thinking existant en temps réel."""
        self.thinking_textbox.configure(state="normal")
        self.thinking_textbox.insert("end", text)
        self.thinking_textbox.configure(state="disabled")
        
        # Auto-scroll vers le bas
        self.thinking_textbox.see("end")
        
        # Ajustement périodique de la hauteur (pas à chaque token pour perf)
        # self.after(100, self._adjust_thinking_textbox_height)
```

---

## 📝 Modifications requises dans `ui/panels.py` (Classe `MainPanel`)

Il faut gérer l'état d'un "message en cours de génération".

### 1. Ajouter l'état de streaming dans `__init__`
```python
self.streaming_state = {
    "active": False,
    "current_container": None,      # Le container du message global
    "thinking_widget": None,        # Widget thinking actif
    "response_textbox": None,       # Textbox temporaire pour la réponse
    "full_content_buffer": "",      # Accumulateur pour le parsing final
    "full_thinking_buffer": ""      # Accumulateur thinking
}
```

### 2. Nouvelles méthodes de gestion du Stream

Ajouter ces méthodes à `MainPanel` :

#### `start_streaming_message(self, target="Chat Principal")`
*   Initialise `self.streaming_state`.
*   Crée un `ResponseContainer` (ou Frame) dans le scrollview cible.
*   Crée un `ThinkingWidget` (vide et caché ou visible) et le stocke dans `streaming_state`.
*   Crée un `CTkTextbox` (vide) pour la réponse et le stocke dans `streaming_state`.

#### `update_streaming_message(self, chunk, is_thinking=False)`
*   **Si `is_thinking` est True :**
    *   Appelle `self.streaming_state["thinking_widget"].append_text(chunk)`.
    *   Met à jour `full_thinking_buffer`.
    *   Assure que le thinking widget est visible/expand si c'est le premier chunk.
*   **Si `is_thinking` est False :**
    *   Appelle `self.streaming_state["response_textbox"].insert("end", chunk)`.
    *   Force le scroll vers le bas du container principal.
    *   Met à jour `full_content_buffer`.

#### `finalize_streaming_message(self)`
*   C'est l'étape critique. Elle transforme le brouillon en version propre.
*   Détruit `self.streaming_state["response_textbox"]`.
*   Appelle `log_chat` (ou une logique similaire) avec `full_content_buffer` pour générer les widgets riches (Markdown, Code) à la place de la textbox temporaire.
*   Conserve le `ThinkingWidget` (déjà rempli) ou le met à jour si nécessaire.
*   Reset `self.streaming_state`.

---

## 🔄 Intégration dans la boucle principale (`run.py` ou `ui/main_window.py`)

Le worker émet des événements via `task_queue`. Il faut intercepter ces événements pour piloter `MainPanel`.

Actuellement, le worker envoie probablement un gros bloc à la fin. Il faut vérifier que le worker émet bien des événements de type `stream_chunk`.

Si le worker envoie :
*   `{"type": "stream_start"}` -> Appeler `panel.start_streaming_message()`
*   `{"type": "stream_chunk", "content": "...", "is_thinking": bool}` -> Appeler `panel.update_streaming_message()`
*   `{"type": "stream_end"}` -> Appeler `panel.finalize_streaming_message()`

---

## ⚠️ Points d'attention pour Cursor

1.  **Thread Safety :** Les mises à jour UI (`insert`, `configure`) doivent impérativement être faites dans le thread principal (via `after` ou la boucle d'événements existante).
2.  **Performance :** Ne pas recalculer la hauteur des widgets (`_adjust_height`) à chaque token. Utiliser un throttle (ex: toutes les 100ms ou tous les 50 tokens).
3.  **Scroll :** Le chat doit scroller automatiquement vers le bas tant que l'utilisateur n'a pas scrollé manuellement vers le haut (auto-scroll locking).

## 📋 Checklist pour Cursor

1.  [ ] Modifier `ui/widgets.py` : Ajouter `append_text` à `ThinkingWidget`.
2.  [ ] Modifier `ui/panels.py` : Implémenter la machine à états `streaming_state` et les méthodes `start/update/finalize`.
3.  [ ] Vérifier `worker/core.py` (si accessible) pour s'assurer qu'il émet bien les chunks vers la queue UI, sinon adapter `ui/main_window.py` pour traiter les messages de stream existants.

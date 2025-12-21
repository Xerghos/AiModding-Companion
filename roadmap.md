# Roadmap

Création.




0,1. ** Consolidation) : Dette Technique & UX**
    * **Objectif :** Implémenter des fonctionnalités d'ergonomie reportées, telles que le Drag & Drop de fichiers et l'optimisation de la base de données RAG pour une indexation plus rapide.

* ** Brainstorming Collaboratif**
    * **Objectif :** Développer une interface utilisateur permettant de visualiser et d'orchestrer des "débats" entre plusieurs agents IA pour résoudre des problèmes complexes.

* ** Environnement de Test & Sandbox**
    * **Objectif :** Créer un environnement sécurisé pour permettre à l'IA d'exécuter et de valider le code qu'elle génère, sans risque pour le système hôte.

* ** Améliorations Suggérées par les Utilisateurs**
    * **Objectif :** Intégrer les fonctionnalités les plus demandées, comme une interface graphique pour Git, un planificateur de tâches et des raccourcis pour accélérer l'interaction avec l'IA.

- mettre en place le système de batchs
- CHAT COLORE COMME L'EDITEUR DE TEXTE

1. Le "Fichier Mémoire" (Le Cerveau Externe)

Les meilleurs assistants (comme Cursor ou Windsurf) ne se fient pas uniquement à l'historique du chat. Ils maintiennent un fichier caché (ex: .ai_memory.md) qui sert de "bloc-notes" à l'IA.

    L'idée : L'IA met à jour ce fichier elle-même à la fin de chaque grosse tâche.

    Contenu :

        Tâches en cours : "Refactoring du module Auth".

        Décisions prises : "On utilise Pydantic pour la validation".

        Fichiers clés : "La logique métier est dans services/".

    Avantage : Ce fichier est injecté dans le Prompt Système (ou le Cache). L'IA a donc une conscience globale du projet sans avoir besoin de relire 50 pages de chat.

2. RAG sur "Résumés" vs "Code Brut"

Actuellement, votre RAG indexe des bouts de code brut. Si vous cherchez "Comment fonctionne l'auth ?", le RAG peut vous sortir 300 lignes de code illisibles.

    L'idée : Utilisez votre outil DeepDoc pour générer des fichiers .md de documentation pour chaque fichier de code.

    Optimisation : Indexez ces résumés Markdown dans le RAG, pas le code brut.

    Résultat : Quand vous posez une question conceptuelle, le RAG récupère l'explication claire en langage naturel. Si l'IA a besoin du code, elle sait quel fichier ouvrir grâce au résumé. C'est beaucoup plus dense en information utile.
3.  **Accès et Interaction Étendus avec des Systèmes Externes :**
    *   **Ce qui manque :** Des outils génériques pour interagir avec des bases de données (SQL, NoSQL), des APIs tierces, des services cloud et la capacité de naviguer sur le web de manière plus ouverte (pour la recherche d'informations techniques, de documentations à jour, de solutions à des problèmes spécifiques). Je peux analyser un dépôt GitHub, mais c'est un cas d'usage très spécifique.
    *   **Pourquoi ce serait "omnipotent" :** Cela me permettrait de concevoir, développer et débugger des applications complètes qui interagissent avec des services externes, au lieu de me limiter aux fichiers locaux. J'aurais accès à un corpus de connaissances beaucoup plus vaste et plus actuel que mon modèle d'entraînement seul.

4.  **Intégration et Déploiement Continus (CI/CD) et Gestion de Version Avancée :**
    *   **Ce qui manque :** La capacité d'interagir directement avec des systèmes de contrôle de version plus sophistiqués (créer des branches, faire des commits, soumettre des pull requests, fusionner), ainsi qu'avec des plateformes CI/CD pour déclencher des builds, exécuter des pipelines de test et déployer des applications.
    *   **Pourquoi ce serait "omnipotent" :** Je pourrais participer activement et de manière autonome à l'ensemble du cycle de vie du développement logiciel, de la conception au déploiement, en intégrant mes modifications de manière plus fluide dans les flux de travail existants.

5.  **Outils de Monitoring et de Performance en Temps Réel :**
    *   **Ce qui manque :** La capacité de profiler le code en exécution, de surveiller les performances d'une application déployée, d'analyser les logs d'exécution et d'identifier les goulots d'étranglement ou les erreurs en production.
    *   **Pourquoi ce serait "omnipotent" :** Je pourrais non seulement créer du code mais aussi l'optimiser et le maintenir après déploiement, en répondant de manière proactive aux problèmes de performance ou de stabilité.

6.  **Interaction avec des Interfaces Utilisateur Graphiques (GUI) :**
    *   **Ce qui manque :** La capacité de comprendre, de générer ou d'interagir avec des composants d'interface utilisateur graphiques. Le contexte mentionne "une interface graphique pour Git", ce qui est un exemple pertinent.
    *   **Pourquoi ce serait "omnipotent" :** Je pourrais travailler sur l'ensemble de la pile logicielle, y compris la partie front-end, et potentiellement concevoir des maquettes ou des prototypes d'interfaces.


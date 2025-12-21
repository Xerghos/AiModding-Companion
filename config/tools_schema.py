# config/tools_schema.py

# Définition complète des schémas d'outils pour Gemini/Groq
# Ce fichier sert de contrat d'interface.

TOOLS_SCHEMA = [
    # --- FILESYSTEM (Gestion de fichiers) ---
    # NOTE: lister_outils est retiré de TOOLS_SCHEMA car l'IA n'en a pas besoin via le Native Tool Calling
    # Elle a déjà accès à tous les outils via le système natif. lister_outils reste disponible via le dispatcher texte (!list_tools)
    {
        "name": "lister_arborescence",
        "description": "Liste l'arborescence des fichiers et dossiers du projet sous forme d'arbre indenté. Filtre automatiquement les dossiers système (.git, __pycache__, venv, etc.) et limite la profondeur d'exploration. Utilisez '.' pour la racine du projet. Utile pour explorer la structure du projet avant de travailler sur des fichiers spécifiques.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "chemin_relatif": {
                    "type": "STRING",
                    "description": "Chemin du dossier à explorer ('.' pour la racine)."
                }
            },
            "required": ["chemin_relatif"]
        }
    },
    {
        "name": "lire_fichier",
        "description": "Lit le contenu complet d'un fichier texte avec résolution intelligente de chemin. Si le fichier n'est pas trouvé directement, effectue une recherche dans le projet pour trouver le fichier correspondant. Ne fonctionne que pour les fichiers texte (UTF-8). Retourne une erreur pour les fichiers binaires ou les encodages non supportés. Utilisez cet outil pour lire le contenu d'un fichier avant de le modifier.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "chemin": {
                    "type": "STRING",
                    "description": "Chemin relatif du fichier (ex: 'config/settings.py')."
                }
            },
            "required": ["chemin"]
        }
    },
    {
        "name": "lire_fichiers",
        "description": "Lit plusieurs fichiers en une seule opération, retournant leur contenu concaténé. Accepte soit un chemin unique (string) soit une liste de chemins. Utile pour charger plusieurs fichiers liés simultanément (ex: tous les fichiers d'un module). Chaque fichier est séparé par une ligne vide dans la sortie. La résolution intelligente de chemin s'applique à chaque fichier individuellement.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "chemins": {
                    "type": "STRING",
                    "description": "Chemin unique ou liste de chemins relatifs séparés par des virgules (ex: 'config/settings.py,config/paths.py')."
                }
            },
            "required": ["chemins"]
        }
    },
    {
        "name": "ecrire_fichier",
        "description": "Écrit du contenu dans un fichier, créant le fichier s'il n'existe pas ou écrasant l'existant. Crée automatiquement les dossiers parents si nécessaire. Pour les fichiers Python, vérifie la syntaxe avant écriture et refuse l'opération si invalide. Réindexe automatiquement le fichier dans la base RAG après écriture pour que les modifications soient disponibles dans la recherche sémantique. Utilisez cet outil pour créer de nouveaux fichiers ou remplacer complètement le contenu d'un fichier existant.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "chemin": {
                    "type": "STRING",
                    "description": "Chemin relatif du fichier cible."
                },
                "contenu": {
                    "type": "STRING",
                    "description": "Contenu complet à écrire dans le fichier."
                }
            },
            "required": ["chemin", "contenu"]
        }
    },
    {
        "name": "comparer_fichiers",
        "description": "Compare deux fichiers et retourne un diff unifié (format unified diff) montrant les différences ligne par ligne. Utile pour vérifier les changements avant ou après une modification, ou pour comprendre les différences entre deux versions d'un fichier. Le format de sortie suit le standard unified diff avec annotations de contexte.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "source": {
                    "type": "STRING",
                    "description": "Chemin du fichier source (version originale)."
                },
                "destination": {
                    "type": "STRING",
                    "description": "Chemin du fichier à comparer (version modifiée)."
                }
            },
            "required": ["source", "destination"]
        }
    },
    {
        "name": "creer_dossier",
        "description": "Crée un dossier et tous ses dossiers parents si nécessaire (création récursive). Ne fait rien si le dossier existe déjà. Respecte les vérifications de sécurité pour empêcher la création en dehors du projet. Utilisez cet outil pour créer la structure de dossiers nécessaire avant d'écrire des fichiers.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "chemin": {
                    "type": "STRING",
                    "description": "Chemin relatif du dossier à créer."
                }
            },
            "required": ["chemin"]
        }
    },
    {
        "name": "supprimer_fichier",
        "description": "Supprime définitivement un fichier du système de fichiers. Action irréversible - le fichier ne peut être récupéré que via un backup. Respecte les vérifications de sécurité et refuse la suppression des fichiers protégés (définis dans la configuration). Ne fonctionne que sur les fichiers, pas sur les dossiers (utilisez des outils système pour supprimer des dossiers).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "chemin": {
                    "type": "STRING",
                    "description": "Chemin relatif du fichier à supprimer."
                }
            },
            "required": ["chemin"]
        }
    },
    {
        "name": "deplacer_fichier",
        "description": "Déplace ou renomme un fichier vers une nouvelle destination. Crée automatiquement les dossiers parents de la destination si nécessaire. Si la destination existe déjà, elle sera écrasée. Cette opération est atomique : le fichier est déplacé, pas copié puis supprimé. Utilisez cet outil pour réorganiser la structure du projet ou renommer des fichiers.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "source": {
                    "type": "STRING",
                    "description": "Chemin actuel du fichier."
                },
                "destination": {
                    "type": "STRING",
                    "description": "Nouveau chemin ou nouveau nom du fichier."
                }
            },
            "required": ["source", "destination"]
        }
    },
    {
        "name": "copier_fichier",
        "description": "Crée une copie d'un fichier vers une nouvelle destination. Le fichier source reste intact. Crée automatiquement les dossiers parents de la destination si nécessaire. Si la destination existe déjà, elle sera écrasée par la copie. Utilisez cet outil pour dupliquer des fichiers (ex: créer des templates ou des variantes).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "source": {
                    "type": "STRING",
                    "description": "Chemin du fichier source à copier."
                },
                "destination": {
                    "type": "STRING",
                    "description": "Chemin de destination pour la copie."
                }
            },
            "required": ["source", "destination"]
        }
    },
    {
        "name": "rechercher_fichiers",
        "description": "Recherche des fichiers dans le projet par motif glob pattern (ex: '*.py', 'test_*', 'config/*.json'). Effectue une recherche récursive à partir du dossier racine spécifié. Exclut automatiquement les dossiers système (.git, __pycache__, venv, etc.). Retourne une liste des chemins relatifs des fichiers correspondants. Utile pour trouver tous les fichiers d'un type donné ou suivant un pattern de nommage.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "pattern": {
                    "type": "STRING",
                    "description": "Motif glob à rechercher (ex: '*.py', 'test_*', 'config/*.json')."
                },
                "chemin_racine": {
                    "type": "STRING",
                    "description": "Dossier de départ pour la recherche ('.' par défaut)."
                }
            },
            "required": ["pattern"]
        }
    },
    {
        "name": "rechercher_texte",
        "description": "Recherche une chaîne de caractères dans le contenu de tous les fichiers du projet (équivalent à grep). Effectue une recherche récursive insensible à la casse. Retourne pour chaque correspondance le chemin du fichier, le numéro de ligne et un extrait du contenu. Limite les résultats à 200 correspondances pour éviter le flood. Ignore les erreurs d'encodage (fichiers binaires partiels). Utile pour trouver toutes les occurrences d'une fonction, classe ou variable dans le code.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Texte à rechercher (recherche insensible à la casse)."
                },
                "path": {
                    "type": "STRING",
                    "description": "Dossier où chercher ('.' par défaut pour tout le projet)."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "obtenir_infos_fichier",
        "description": "Obtient les métadonnées d'un fichier : taille en octets, date de modification, date de création, permissions. Utile pour vérifier l'état d'un fichier avant de le modifier ou pour diagnostiquer des problèmes de synchronisation.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "chemin": {
                    "type": "STRING",
                    "description": "Chemin relatif du fichier."
                }
            },
            "required": ["chemin"]
        }
    },

    # --- DOCUMENTATION & ARCHITECTURE ---
    {
        "name": "generer_documentation",
        "description": "Génère la documentation technique complète d'un fichier ou dossier en mode 'atomique' (détaillé) ou 'resume' (synthétique). En mode atomique, crée une documentation Markdown complète avec signatures, paramètres, retours, logique interne et exemples. La documentation est sauvegardée dans Documentation/Reference/ avec le nom du fichier. Vérifie automatiquement les hash pour éviter de régénérer une documentation inchangée. Exclut automatiquement les fichiers système et les dossiers protégés. Le processus est multi-threadé pour les dossiers avec plusieurs fichiers. Utilisez cet outil pour créer ou mettre à jour la documentation du projet.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "cible": {
                    "type": "STRING",
                    "description": "Chemin du fichier ou dossier à documenter (ex: 'features/core.py' ou 'features')."
                },
                "mode": {
                    "type": "STRING",
                    "description": "Mode de documentation : 'atomique' pour une documentation détaillée complète, 'resume' pour un résumé synthétique.",
                    "enum": ["atomique", "resume"] 
                }
            },
            "required": ["cible", "mode"]
        }
    },
    {
        "name": "rechercher_documentation",
        "description": "Recherche dans la documentation existante (fichiers Markdown dans Documentation/Reference/). Effectue une recherche textuelle dans tous les fichiers de documentation générés. Utile pour trouver des informations déjà documentées sur une fonction, classe ou module avant de créer de nouvelles documentation.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "requete": {
                    "type": "STRING",
                    "description": "Mots-clés ou question à rechercher dans la documentation."
                }
            },
            "required": ["requete"]
        }
    },
    {
        "name": "update_architecture",
        "description": "Régénère la carte architecturale du projet en analysant le code source. Lance un script externe (scripts/generate_arch_map.py) qui analyse la structure du code et génère un fichier JSON (config/architecture_map.json) décrivant les domaines, modules et dépendances. Cette carte est utilisée par d'autres outils comme charger_contexte_domaine pour charger automatiquement les fichiers liés à un domaine. Déclenchez cette opération après des changements architecturaux importants.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    
    # --- WEB & NAVIGATION ---
    {
        "name": "web_search",
        "description": "Effectue une recherche sur Google et extrait les top résultats avec titre, lien et extrait. Utilise un navigateur headless (Playwright) pour contourner les limitations API. Retourne les 6 premiers résultats pertinents. Peut être bloqué par Google si trop de requêtes sont effectuées. Utilisez cet outil pour rechercher des informations récentes, de la documentation externe ou des solutions à des problèmes techniques qui ne sont pas dans le projet.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query": {
                    "type": "STRING",
                    "description": "Mots-clés de recherche Google."
                }
            },
            "required": ["query"]
        }
    },
    {
        "name": "web_goto",
        "description": "Visite une page web et en extrait le contenu textuel complet. Nettoie automatiquement le HTML (supprime scripts, styles, navigation) pour ne garder que le contenu utile. Si le contenu est long (>4000 caractères), génère automatiquement un résumé pour éviter de saturer le contexte. Utilise un navigateur headless avec timeout de 20 secondes. Le contenu extrait est token-friendly (texte pur). Utilisez cet outil pour lire de la documentation en ligne, des articles ou des pages web spécifiques identifiées via web_search.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "url": {
                    "type": "STRING",
                    "description": "URL complète de la page web (doit commencer par https:// ou http://)."
                }
            },
            "required": ["url"]
        }
    },
    {
        "name": "web_screen",
        "description": "Prend une capture d'écran de la page web actuellement chargée dans le navigateur. Nécessite qu'une page soit déjà ouverte via web_goto. Utile pour le débogage ou pour visualiser l'état d'une page web. Sauvegarde l'image au format PNG. Si aucun nom de fichier n'est fourni, génère un nom automatique basé sur le timestamp.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "filename": {
                    "type": "STRING",
                    "description": "Nom du fichier image à sauvegarder (optionnel, génère un nom automatique si omis)."
                }
            }
        }
    },
    
    # --- BACKUP & SYSTEM ---
    {
        "name": "backup_projet",
        "description": "Crée une archive ZIP complète du projet entier dans le dossier backups/. Exclut automatiquement les dossiers système (.git, __pycache__, venv, node_modules, etc.) et les fichiers temporaires. Implémente un cooldown entre les backups pour éviter la création excessive de sauvegardes. Utilisez le paramètre 'force' pour outrepasser le cooldown si nécessaire. Chaque backup est horodaté et peut inclure un commentaire optionnel. Les backups sont essentiels avant des opérations destructives comme restaurer_backup ou des refactorings majeurs.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "commentaire": {
                    "type": "STRING",
                    "description": "Commentaire optionnel à associer au backup (utile pour documenter pourquoi ce backup a été créé)."
                }
            }
        }
    },
    {
        "name": "creer_backup",
        "description": "Alias de backup_projet. Crée une archive ZIP complète du projet avec les mêmes fonctionnalités : exclusions automatiques, cooldown, horodatage et commentaire optionnel.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "commentaire": {
                    "type": "STRING",
                    "description": "Commentaire optionnel pour le backup."
                }
            }
        }
    },
    {
        "name": "restaurer_backup",
        "description": "Restaure un backup précédemment créé. ATTENTION : Cette opération est DESTRUCTIVE - elle écrase complètement le projet actuel avec le contenu du backup. Crée automatiquement un backup de sécurité juste avant la restauration pour permettre un rollback. Nécessite le nom exact du fichier ZIP de backup (obtenez-le via lister_backups). Après restauration, recharge automatiquement l'interface. Utilisez avec extrême précaution - il n'y a pas de confirmation interactive.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "nom_backup": {
                    "type": "STRING",
                    "description": "Nom complet du fichier ZIP de backup à restaurer (ex: 'backup_2025-12-20_143022.zip'). Utilisez lister_backups pour obtenir les noms disponibles."
                }
            },
            "required": ["nom_backup"]
        }
    },
    {
        "name": "lister_backups",
        "description": "Liste tous les backups disponibles dans le dossier backups/, triés par date (plus récent en premier). Affiche pour chaque backup : la date de création, le nom du fichier et la taille. Utile pour identifier le backup à restaurer ou pour vérifier l'historique des sauvegardes. Limite l'affichage à 10 backups dans le rapport pour éviter le flood, mais tous sont disponibles via l'interface.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },  
    {
        "name": "lire_logs",
        "description": "Lit les dernières lignes des logs système pour diagnostiquer des problèmes ou vérifier l'activité récente. Par défaut, lit 50 lignes. Les logs incluent toutes les activités du système (actions des outils, erreurs, warnings, etc.). Utile pour comprendre ce qui s'est passé lors d'une opération ou pour déboguer des erreurs.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "lignes": {
                    "type": "INTEGER",
                    "description": "Nombre de lignes de log à lire (50 par défaut)."
                }
            }
        }
    },

    # --- CODE QUALITY & ANALYSIS ---
    {
        "name": "audit_qualite",
        "description": "Effectue un audit statique de code (linting) et des vérifications de sécurité sur un fichier. Analyse le code pour détecter les erreurs de style, les pratiques dangereuses, les vulnérabilités potentielles et les problèmes de qualité. Peut être ciblé avec une consigne spécifique pour se concentrer sur un aspect particulier (ex: 'vérifier la gestion des erreurs', 'chercher les fuites mémoire'). Retourne un rapport détaillé avec les problèmes identifiés et des suggestions d'amélioration.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "chemin": {
                    "type": "STRING",
                    "description": "Chemin relatif du fichier à auditer."
                },
                "consigne": {
                    "type": "STRING",
                    "description": "Consigne optionnelle pour cibler l'audit sur un aspect spécifique (ex: 'vérifier sécurité', 'style PEP8')."
                }
            },
            "required": ["chemin"]
        }
    },
    {
        "name": "verifier_code",
        "description": "Alias de audit_qualite. Effectue le même audit statique de code et vérifications de sécurité avec les mêmes fonctionnalités.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "chemin": {
                    "type": "STRING",
                    "description": "Chemin relatif du fichier à vérifier."
                },
                "consigne": {
                    "type": "STRING",
                    "description": "Consigne optionnelle pour cibler la vérification (ex: 'focus sécurité', 'style')."
                }
            },
            "required": ["chemin"]
        }
    },
    {
        "name": "analyser_code",
        "description": "Effectue une analyse structurelle et sémantique approfondie du code pour comprendre l'architecture, les dépendances, les patterns utilisés et la logique interne. Analyse l'AST (Abstract Syntax Tree) et détecte les relations entre classes, fonctions et modules. Supporte les fichiers uniques ou les dossiers (limité à 10 fichiers pour une analyse approfondie). Retourne un rapport détaillé sur la structure, les dépendances, les responsabilités et les points d'attention. Utile pour comprendre un code legacy ou planifier un refactoring.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "chemin": {
                    "type": "STRING",
                    "description": "Chemin du fichier ou dossier à analyser."
                }
            },
            "required": ["chemin"]
        }
    },
    {
        "name": "generer_tests",
        "description": "Génère des tests unitaires pour un fichier source donné. Analyse le code source pour identifier les fonctions, classes et méthodes à tester, puis génère des tests couvrant les cas normaux et les cas limites. Utilise un framework de test standard (pytest-style). Le code généré est prêt à être exécuté. Utile pour améliorer la couverture de tests d'un module ou pour créer des tests de régression après un refactoring.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "chemin_source": {
                    "type": "STRING",
                    "description": "Chemin du fichier source pour lequel générer les tests."
                }
            },
            "required": ["chemin_source"]
        }
    },
    
    # --- REFACTORING ---
    {
        "name": "refactoriser_code",
        "description": "Analyse et propose ou applique un refactoring sur un fichier ou dossier. Deux modes d'opération : si auto_apply=True et cible est un fichier unique, applique directement les modifications (Fast-Track) via modifier_fichier avec backup automatique. Sinon, génère un PLAN DE REFACTORING détaillé expliquant les étapes, les classes à créer/modifier, les risques et l'approche recommandée. Pour les dossiers, analyse jusqu'à 60k caractères de contexte. Le plan peut ensuite être appliqué manuellement ou via modifier_fichier pour chaque fichier. Utilisez cet outil pour améliorer la qualité du code sans changer sa fonctionnalité.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "cible": {
                    "type": "STRING",
                    "description": "Chemin du fichier ou dossier à refactorer."
                },
                "consigne": {
                    "type": "STRING",
                    "description": "Objectif du refactoring (ex: 'Réduire la complexité cyclomatique', 'Extraire les constantes magiques', 'Améliorer la lisibilité')."
                },
                "auto_apply": {
                    "type": "BOOLEAN",
                    "description": "Si True et cible est un fichier unique, applique directement les modifications. Si False ou cible est un dossier, génère seulement un plan de refactoring."
                }
            },
            "required": ["cible", "consigne"]
        }
    },
    {
        "name": "modifier_fichier",
        "description": "Applique une modification ciblée à un fichier existant en utilisant l'IA pour réécrire le code complet selon l'instruction fournie. Crée automatiquement un backup de sécurité avant modification. Vérifie la syntaxe Python avant écriture et refuse l'opération si le code généré est invalide. Réindexe automatiquement le fichier dans la base RAG après modification. L'instruction doit décrire précisément la modification souhaitée (ex: 'Ajoute une méthode validate() à la classe User', 'Corrige la gestion d'erreur dans la fonction parse() pour lever une ValueError au lieu de retourner None'). Ne fonctionne que sur des fichiers, pas sur des dossiers (utilisez refactoriser_code pour les dossiers).",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "chemin": {
                    "type": "STRING",
                    "description": "Chemin relatif du fichier à modifier."
                },
                "instruction": {
                    "type": "STRING",
                    "description": "Description précise et détaillée de la modification à appliquer. Soyez spécifique sur ce qui doit changer, où et comment."
                }
            },
            "required": ["chemin", "instruction"]
        }
    },
    {
        "name": "formater_code",
        "description": "Formate le code selon les standards Python (PEP8, style Black). Corrige l'indentation, l'espacement, l'organisation des imports et la longueur des lignes. Préserve la logique du code - ne modifie que le style, pas le comportement. Utilise l'IA pour appliquer les règles de formatage de manière cohérente. Utile pour uniformiser le style du code après des modifications manuelles ou pour préparer le code avant un commit.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "fichier": {
                    "type": "STRING",
                    "description": "Chemin relatif du fichier à formater."
                }
            },
            "required": ["fichier"]
        }
    },

    # --- PROJECT MANAGEMENT ---
    {
        "name": "generer_plan_technique_atomique",
        "description": "Crée ou met à jour le fichier PLAN_TECHNIQUE_ATOMIQUE.md qui documente l'architecture technique du projet de manière atomique (détaillée). Synchronise intelligemment le plan existant avec l'état actuel du code, en préservant les sections non affectées. Peut être guidé par une consigne optionnelle pour se concentrer sur un aspect spécifique ou une mise à jour particulière. Ce plan sert de référence technique centrale pour le projet.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "instruction": {
                    "type": "STRING",
                    "description": "Consigne optionnelle pour guider la génération ou la mise à jour du plan (ex: 'Focus sur les changements de cette semaine', 'Documenter le nouveau système RAG')."
                }
            }
        }
    },
    {
        "name": "generer_changelog_append_only",
        "description": "Met à jour le fichier changelogs.md en ajoutant les nouveautés récentes à la fin du fichier (format append-only, pas de réécriture complète). Détecte automatiquement les changements récents dans le projet et les documente de manière structurée. Conserve l'historique complet des changements. Utilisez régulièrement pour maintenir un historique à jour des évolutions du projet.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "generer_roadmap_synthetique",
        "description": "Génère ou met à jour une roadmap de haut niveau résumant les objectifs, priorités et évolutions prévues du projet. Format synthétique et orienté vision plutôt que détails techniques. Peut être guidé par une consigne optionnelle pour se concentrer sur un horizon temporel ou un domaine spécifique. Utile pour avoir une vue d'ensemble de la direction du projet.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "instruction": {
                    "type": "STRING",
                    "description": "Consigne optionnelle pour orienter la roadmap (ex: 'Focus Q1 2025', 'Priorités sécurité')."
                }
            }
        }
    },
    {
        "name": "synthese_historique",
        "description": "Génère un résumé de l'activité récente du projet basé sur l'historique des conversations et actions. Analyse l'historique du chat pour extraire les changements, décisions et événements importants. Peut être filtré par un mot-clé pour se concentrer sur un thème spécifique (ex: 'RAG', 'UI', 'refactoring'). Utile pour avoir un aperçu rapide de ce qui s'est passé récemment ou pour préparer un rapport d'activité.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "filtre": {
                    "type": "STRING",
                    "description": "Mot-clé optionnel pour filtrer la synthèse sur un thème spécifique (ex: 'RAG', 'documentation', 'bugfix')."
                }
            }
        }
    },
    {
        "name": "analyser_depot_github",
        "description": "Clone temporairement un dépôt GitHub distant, analyse son contenu et génère un rapport Markdown détaillé. Analyse la structure du projet, la stack technique, la qualité du code et identifie les points d'intérêt. Nettoie automatiquement le clone temporaire après l'analyse. Le rapport est sauvegardé localement avec le nom 'analyse_[nom_depot].md'. Utile pour auditer des dépendances externes, comprendre des projets références ou évaluer des contributions externes.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "url": {
                    "type": "STRING",
                    "description": "URL HTTPS complète du dépôt GitHub (ex: 'https://github.com/user/repo')."
                }
            },
            "required": ["url"]
        }
    },

    # --- CONTEXT & MEMORY ---
    {
        "name": "charger_contexte",
        "description": "Recharge le contexte projet en mode 'light' (contexte minimal) ou 'full' (contexte complet). Outil legacy - il est recommandé d'utiliser charger_contexte_domaine pour un chargement plus ciblé et efficace. Le mode 'light' charge seulement les fichiers essentiels, tandis que 'full' charge une vue complète du projet. Peut être utile pour forcer un rechargement complet du contexte après des changements majeurs.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "mode": {
                    "type": "STRING",
                    "description": "Mode de chargement : 'light' pour un contexte minimal rapide, 'full' pour un contexte complet (plus lent mais plus exhaustif).",
                    "enum": ["light", "full"]
                }
            }
        }
    },
    {
        "name": "charger_contexte_domaine",
        "description": "Charge automatiquement tous les fichiers liés à un domaine architectural spécifique en utilisant la carte architecturale (architecture_map.json). Mappe le domaine aux fichiers correspondants et charge leur contenu. Exemples de domaines : 'logging', 'ui_core', 'rag', 'database'. Plus efficace que charger_contexte car il se concentre sur un domaine spécifique. Nécessite que update_architecture ait été exécuté récemment pour que la carte soit à jour.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "domaine": {
                    "type": "STRING",
                    "description": "Nom du domaine architectural à charger (ex: 'logging', 'ui_core', 'rag', 'database'). Consultez architecture_map.json pour les domaines disponibles."
                }
            },
            "required": ["domaine"]
        }
    },
    {
        "name": "sauvegarder_memoire",
        "description": "Enregistre explicitement une information dans la mémoire sémantique à long terme (LTM). L'information est vectorisée et stockée dans la base RAG pour être retrouvée ultérieurement via rechercher_memoire. Format clé-valeur : la clé identifie le sujet et la valeur contient l'information à retenir. Utile pour mémoriser des décisions architecturales, des conventions de code, des configurations spéciales ou toute information importante qui doit persister entre les sessions.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "cle": {
                    "type": "STRING",
                    "description": "Clé ou sujet identifiant l'information (ex: 'architecture_rag', 'convention_naming')."
                },
                "valeur": {
                    "type": "STRING",
                    "description": "Information à mémoriser (peut être un texte descriptif complet)."
                }
            },
            "required": ["cle", "valeur"]
        }
    },
    {
        "name": "rechercher_memoire",
        "description": "Interroge la mémoire sémantique à long terme (LTM) pour retrouver des informations précédemment mémorisées. Effectue une recherche vectorielle pour trouver les souvenirs les plus pertinents à la requête. Retourne les 3 résultats les plus pertinents. Utile pour retrouver des décisions passées, des conventions établies ou des informations contextuelles importantes qui ont été mémorisées via sauvegarder_memoire ou automatiquement par le système.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "requete": {
                    "type": "STRING",
                    "description": "Question ou sujet à rechercher dans la mémoire (ex: 'Quelle est la convention de nommage ?', 'architecture RAG')."
                }
            },
            "required": ["requete"]
        }
    },
    
    # --- RAG (Retrieval-Augmented Generation) ---
    {
        "name": "reconstruire_base_vectorielle",
        "description": "Réindexe complètement tous les fichiers du projet dans la base RAG (Recherche Augmentée par Génération). Scanne tous les fichiers supportés, les découpe en chunks sémantiques (avec Tree-sitter pour Python si disponible), calcule les embeddings vectoriels (FAISS) et les indexe également en recherche full-text (FTS5). Cette opération peut être longue pour de gros projets. Utile après des changements majeurs du code, une mise à jour de la structure du projet, ou si la base RAG semble obsolète. La base est utilisée automatiquement par le système RAG pour enrichir le contexte des réponses.",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    },
    {
        "name": "supprimer_base_vectorielle",
        "description": "Supprime complètement la base RAG (fichiers SQLite, index FAISS et mapping). ACTION DESTRUCTIVE - toutes les données indexées seront perdues. Réinitialise la base à vide. Nécessite une reconstruction complète via reconstruire_base_vectorielle pour réutiliser le système RAG. Utilisez cette fonction seulement si vous voulez repartir de zéro (ex: après un changement majeur d'architecture, pour corriger des problèmes de corruption, ou pour libérer de l'espace disque).",
        "parameters": {
            "type": "OBJECT",
            "properties": {}
        }
    }
]

```json
{
  "filename": "settings.json",
  "documentation": [
    {
      "section": "Configuration Générale",
      "description": "Ce fichier de configuration centralise les paramètres globaux de l'application, incluant les clés d'API pour différents fournisseurs d'IA, la configuration du moteur d'IA principal, les paramètres système de base, la configuration des agents et des swarms, les raccourcis clavier et les canaux de journalisation.",
      "metadata": {
        "generated_at": "2025-12-15 22:52:09",
        "version": "Ultimate Graph V2"
      }
    },
    {
      "section": "Clés d'API",
      "description": "Section pour stocker les clés d'API nécessaires à l'authentification auprès de divers services d'IA. Les clés doivent être fournies pour que les fonctionnalités correspondantes fonctionnent.",
      "parameters": {
        "api_keys.google_gemini": {
          "type": "string",
          "description": "Clé API pour Google Gemini.",
          "default": "",
          "required": false
        },
        "api_keys.openai": {
          "type": "string",
          "description": "Clé API pour OpenAI.",
          "default": "",
          "required": false
        },
        "api_keys.anthropic": {
          "type": "string",
          "description": "Clé API pour Anthropic.",
          "default": "",
          "required": false
        },
        "api_keys.mistral": {
          "type": "string",
          "description": "Clé API pour Mistral AI.",
          "default": "",
          "required": false
        },
        "api_keys.groq": {
          "type": "string",
          "description": "Clé API pour Groq.",
          "default": "",
          "required": false
        },
        "api_keys.openrouter": {
          "type": "string",
          "description": "Clé API pour OpenRouter.",
          "default": "",
          "required": false
        },
        "api_keys.huggingface": {
          "type": "string",
          "description": "Clé API pour Hugging Face.",
          "default": "",
          "required": false
        }
      }
    },
    {
      "section": "Moteur IA",
      "description": "Configure le moteur d'IA principal utilisé par l'application, y compris le fournisseur, le modèle, la température et la limite de tokens.",
      "parameters": {
        "ai_engine.provider": {
          "type": "string",
          "description": "Fournisseur du modèle d'IA à utiliser (ex: google_gemini, openai).",
          "default": "google_gemini",
          "required": true
        },
        "ai_engine.model": {
          "type": "string",
          "description": "Modèle d'IA spécifique à utiliser.",
          "default": "gemini-1.5-flash",
          "required": true
        },
        "ai_engine.temperature": {
          "type": "number",
          "description": "Contrôle la créativité des réponses de l'IA. Une valeur plus élevée donne des résultats plus aléatoires.",
          "default": 0.7,
          "required": true,
          "range": "0.0 - 1.0"
        },
        "ai_engine.max_tokens": {
          "type": "integer",
          "description": "Le nombre maximum de tokens que l'IA peut générer dans une réponse.",
          "default": 2048,
          "required": true
        },
        "ai_engine.cloud_models_registry": {
          "type": "object",
          "description": "Mappage des alias de modèles ('fast', 'smart', 'coder', 'creative') aux noms de modèles spécifiques des fournisseurs cloud.",
          "parameters": {
            "fast": {
              "type": "string",
              "description": "Modèle rapide par défaut.",
              "default": "gemini-1.5-flash",
              "required": true
            },
            "smart": {
              "type": "string",
              "description": "Modèle intelligent par défaut.",
              "default": "gemini-1.5-pro",
              "required": true
            },
            "coder": {
              "type": "string",
              "description": "Modèle optimisé pour le codage.",
              "default": "gemini-1.5-pro",
              "required": true
            },
            "creative": {
              "type": "string",
              "description": "Modèle optimisé pour la créativité.",
              "default": "gemini-1.5-flash",
              "required": true
            }
          }
        }
      }
    },
    {
      "section": "Paramètres Système",
      "description": "Paramètres généraux de l'interface utilisateur et du comportement du système.",
      "parameters": {
        "system_settings.theme": {
          "type": "string",
          "description": "Thème de l'interface utilisateur ('Dark' ou 'Light').",
          "default": "Dark",
          "required": true,
          "enum": ["Dark", "Light"]
        },
        "system_settings.font_size": {
          "type": "integer",
          "description": "Taille de la police pour l'interface utilisateur.",
          "default": 12,
          "required": true
        },
        "system_settings.auto_backup": {
          "type": "boolean",
          "description": "Active ou désactive la sauvegarde automatique des données.",
          "default": true,
          "required": true
        },
        "system_settings.backup_interval": {
          "type": "integer",
          "description": "Intervalle en minutes entre les sauvegardes automatiques.",
          "default": 30,
          "required": true
        },
        "system_settings.max_backups": {
          "type": "integer",
          "description": "Nombre maximum de sauvegardes à conserver.",
          "default": 10,
          "required": true
        },
        "system_settings.rag_enabled": {
          "type": "boolean",
          "description": "Active ou désactive la fonctionnalité Retrieval-Augmented Generation (RAG).",
          "default": true,
          "required": true
        },
        "system_settings.rag_database_path": {
          "type": "string",
          "description": "Chemin d'accès à la base de données utilisée pour RAG.",
          "default": "db/knowledge_base_hybrid",
          "required": true
        },
        "system_settings.max_history_retention": {
          "type": "integer",
          "description": "Nombre maximum de conversations/étapes à conserver dans l'historique.",
          "default": 50,
          "required": true
        }
      }
    },
    {
      "section": "Configuration des Agents",
      "description": "Paramètres spécifiques à la gestion et au comportement des agents IA.",
      "parameters": {
        "agents_config.react_max_steps_cloud": {
          "type": "integer",
          "description": "Nombre maximum d'étapes que les agents peuvent exécuter dans un cycle REAct sur le cloud.",
          "default": 10,
          "required": true
        },
        "agents_config.active_agents": {
          "type": "array",
          "description": "Liste des rôles d'agents actifs dans l'application.",
          "default": ["coder", "architect", "documenter"],
          "required": true,
          "items": {
            "type": "string"
          }
        }
      }
    },
    {
      "section": "Paramètres Swarm",
      "description": "Configuration du comportement et de l'organisation des agents en swarm.",
      "parameters": {
        "swarm_settings.mode": {
          "type": "string",
          "description": "Mode d'organisation du swarm (ex: 'hierarchical', 'flat').",
          "default": "hierarchical",
          "required": true
        },
        "swarm_settings.autonomy_level": {
          "type": "string",
          "description": "Niveau d'autonomie des agents dans le swarm (ex: 'supervised', 'autonomous').",
          "default": "supervised",
          "required": true
        },
        "swarm_settings.role_mapping": {
          "type": "object",
          "description": "Mappage des rôles de swarm aux modèles d'IA spécifiques à utiliser pour ces rôles.",
          "parameters": {
            "manager": {
              "type": "string",
              "description": "Modèle d'IA pour le rôle de manager.",
              "default": "gemini-1.5-pro",
              "required": true
            },
            "coder": {
              "type": "string",
              "description": "Modèle d'IA pour le rôle de coder.",
              "default": "gemini-1.5-flash",
              "required": true
            }
          }
        }
      }
    },
    {
      "section": "Raccourcis Clavier",
      "description": "Configuration des raccourcis clavier pour les actions courantes de l'application.",
      "parameters": {
        "key_bindings.send_message": {
          "type": "string",
          "description": "Raccourci pour envoyer un message.",
          "default": "<Return>",
          "required": true
        },
        "key_bindings.new_line": {
          "type": "string",
          "description": "Raccourci pour insérer un nouveau saut de ligne.",
          "default": "<Shift-Return>",
          "required": true
        },
        "key_bindings.toggle_sidebar": {
          "type": "string",
          "description": "Raccourci pour afficher/masquer la barre latérale.",
          "default": "<Control-b>",
          "required": true
        },
        "key_bindings.focus_input": {
          "type": "string",
          "description": "Raccourci pour placer le curseur dans le champ de saisie.",
          "default": "<Control-l>",
          "required": true
        },
        "key_bindings.close_tab": {
          "type": "string",
          "description": "Raccourci pour fermer l'onglet actuel.",
          "default": "<Control-w>",
          "required": true
        },
        "key_bindings.next_tab": {
          "type": "string",
          "description": "Raccourci pour passer à l'onglet suivant.",
          "default": "<Control-Tab>",
          "required": true
        }
      }
    },
    {
      "section": "Canaux de Journalisation",
      "description": "Contrôle quels canaux de journalisation sont activés pour le débogage et le suivi.",
      "parameters": {
        "logging_channels.SYSTEM": {
          "type": "boolean",
          "description": "Active la journalisation des événements système.",
          "default": true,
          "required": true
        },
        "logging_channels.WORKER": {
          "type": "boolean",
          "description": "Active la journalisation des activités des workers.",
          "default": true,
          "required": true
        },
        "logging_channels.MEMORY": {
          "type": "boolean",
          "description": "Active la journalisation de la gestion de la mémoire.",
          "default": false,
          "required": true
        },
        "logging_channels.NETWORK": {
          "type": "boolean",
          "description": "Active la journalisation des communications réseau.",
          "default": true,
          "required": true
        },
        "logging_channels.UI": {
          "type": "boolean",
          "description": "Active la journalisation des événements de l'interface utilisateur.",
          "default": false,
          "required": true
        },
        "logging_channels.FILES": {
          "type": "boolean",
          "description": "Active la journalisation des opérations sur les fichiers.",
          "default": false,
          "required": true
        },
        "logging_channels.AUDIO": {
          "type": "boolean",
          "description": "Active la journalisation des événements audio.",
          "default": false,
          "required": true
        }
      }
    }
  ]
}
```
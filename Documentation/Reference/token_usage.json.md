# Documentation Technique du Fichier `token_usage.json`

## En-tête

### Titre
Rapport d'Utilisation des Tokens API

### Description concise
Ce fichier JSON contient un rapport détaillé sur l'utilisation des tokens pour les appels à des modèles d'IA. Il agrège les données d'utilisation globalement, par modèle et par clé d'accès (ou identifiant d'utilisateur/projet), distinguant les tokens d'entrée (`in`) et de sortie (`out`).

### Dépendances
Aucune dépendance externe requise pour la lecture du format. Ce fichier est un format de données JSON standard.

## Classes & Fonctions (Structure de Données)

Bien qu'il ne s'agisse pas de code source exécutable, ce fichier JSON représente une structure de données claire. Nous décrivons ici les objets principaux et leurs champs.

### Objet Racine (`token_usage.json`)
Représente l'ensemble du rapport d'utilisation des tokens.

*   **Type**: Objet JSON
*   **Champs**:
    *   `total_global` (Objet): Résumé global de l'utilisation des tokens.
        *   **Description**: Contient les totaux d'utilisation de tokens pour l'ensemble du système.
        *   **Structure**: Voir `Objet: Total Global` ci-dessous.
    *   `by_model` (Objet): Utilisation des tokens agrégée par modèle d'IA.
        *   **Description**: Une collection d'objets où chaque clé est le nom d'un modèle d'IA et chaque valeur est un objet détaillé sur l'utilisation de ce modèle.
        *   **Structure**: Voir `Objet: Utilisation Par Modèle` ci-dessous.
    *   `by_key` (Objet): Utilisation des tokens agrégée par clé d'accès ou identifiant.
        *   **Description**: Une collection d'objets où chaque clé est un identifiant unique (par exemple, une clé API ou un ID utilisateur/projet) et chaque valeur est un objet détaillé sur l'utilisation associée à cet identifiant.
        *   **Structure**: Voir `Objet: Utilisation Par Clé` ci-dessous.

### Objet: Total Global
Détaille l'utilisation totale des tokens sur l'ensemble du système.

*   **Type**: Objet JSON
*   **Champs**:
    *   `in` (Entier):
        *   **Description**: Nombre total de tokens d'entrée (input) consommés globalement.
        *   **Valeur typique**: `11359253`
    *   `out` (Entier):
        *   **Description**: Nombre total de tokens de sortie (output) générés globalement.
        *   **Valeur typique**: `1618331`

### Objet: Utilisation Par Modèle
Décrit l'utilisation des tokens pour un modèle d'IA spécifique.

*   **Type**: Objet JSON (comme valeur des clés dans `by_model`)
*   **Champs**:
    *   `in` (Entier):
        *   **Description**: Nombre total de tokens d'entrée consommés par ce modèle.
        *   **Valeur typique**: `1781252` (pour `gemini-2.5-flash`)
    *   `out` (Entier):
        *   **Description**: Nombre total de tokens de sortie générés par ce modèle.
        *   **Valeur typique**: `732826` (pour `gemini-2.5-flash`)
    *   `calls` (Entier):
        *   **Description**: Nombre d'appels (invocations) effectués à ce modèle.
        *   **Valeur typique**: `395` (pour `gemini-2.5-flash`)

### Objet: Utilisation Par Clé
Décrit l'utilisation des tokens pour une clé d'accès (ou identifiant) spécifique.

*   **Type**: Objet JSON (comme valeur des clés dans `by_key`)
*   **Champs**:
    *   `in` (Entier):
        *   **Description**: Nombre total de tokens d'entrée consommés via cette clé.
        *   **Valeur typique**: `181097` (pour la clé `JxgUJU`)
    *   `out` (Entier):
        *   **Description**: Nombre total de tokens de sortie générés via cette clé.
        *   **Valeur typique**: `13969` (pour la clé `JxgUJU`)
    *   `provider` (Chaîne de caractères):
        *   **Description**: Le fournisseur du service associé à cette clé.
        *   **Valeur typique**: `"gemini"`

## Exemple d'usage

Voici un exemple en Python montrant comment charger et accéder aux données de ce fichier JSON.

```python
import json

def load_token_usage_data(filepath="token_usage.json"):
    """
    Charge les données d'utilisation des tokens à partir d'un fichier JSON.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def analyze_token_usage(data):
    """
    Analyse et affiche des statistiques clés sur l'utilisation des tokens.
    """
    print("--- Rapport d'Utilisation des Tokens ---")

    # Utilisation globale
    total_in = data["total_global"]["in"]
    total_out = data["total_global"]["out"]
    print(f"\nUtilisation Globale:")
    print(f"  Tokens d'entrée (Input): {total_in}")
    print(f"  Tokens de sortie (Output): {total_out}")
    print(f"  Total tokens: {total_in + total_out}")

    # Utilisation par modèle
    print(f"\nUtilisation par Modèle:")
    for model_name, usage in data["by_model"].items():
        model_in = usage["in"]
        model_out = usage["out"]
        model_calls = usage["calls"]
        print(f"  Modèle: {model_name}")
        print(f"    Tokens d'entrée: {model_in}")
        print(f"    Tokens de sortie: {model_out}")
        print(f"    Appels API: {model_calls}")
        print(f"    Total tokens: {model_in + model_out}")

    # Utilisation par clé (les 5 premières pour l'exemple)
    print(f"\nUtilisation par Clé (Top 5):")
    sorted_keys = sorted(data["by_key"].items(), key=lambda item: item[1]["in"] + item[1]["out"], reverse=True)
    for i, (key_id, usage) in enumerate(sorted_keys[:5]):
        key_in = usage["in"]
        key_out = usage["out"]
        provider = usage["provider"]
        print(f"  Clé: {key_id} (Fournisseur: {provider})")
        print(f"    Tokens d'entrée: {key_in}")
        print(f"    Tokens de sortie: {key_out}")
        print(f"    Total tokens: {key_in + key_out}")

# Simuler le contenu du fichier (pour un test sans fichier réel)
file_content = """
{
  "total_global": {
    "in": 11359253,
    "out": 1618331
  },
  "by_model": {
    "gemini-2.5-flash": {
      "in": 1781252,
      "out": 732826,
      "calls": 395
    },
    "gemini-2.5-flash-lite": {
      "in": 2797876,
      "out": 772348,
      "calls": 625
    },
    "gemini-2.5-pro": {
      "in": 1090,
      "out": 1038,
      "calls": 1
    },
    "deepseek-reasoner": {
      "in": 6360748,
      "out": 107017,
      "calls": 348
    },
    "deepseek-chat": {
      "in": 51675,
      "out": 446,
      "calls": 9
    },
    "gemini-3-flash-preview": {
      "in": 366612,
      "out": 4656,
      "calls": 58
    }
  },
  "by_key": {
    "JxgUJU": {
      "in": 181097,
      "out": 13969,
      "provider": "gemini"
    },
    "TycB8U": {
      "in": 47407,
      "out": 84562,
      "provider": "gemini"
    },
    "WAsiqQ": {
      "in": 75516,
      "out": 16903,
      "provider": "gemini"
    },
    "mi-OVY": {
      "in": 52838,
      "out": 24476,
      "provider": "gemini"
    },
    "XmBqmY": {
      "in": 131519,
      "out": 32512,
      "provider": "gemini"
    },
    "eRnXuE": {
      "in": 97755,
      "out": 24308,
      "provider": "gemini"
    },
    "KD6WWI": {
      "in": 123817,
      "out": 22181,
      "provider": "gemini"
    },
    "L-3sq4": {
      "in": 39535,
      "out": 20534,
      "provider": "gemini"
    },
    "3ljmv8": {
      "in": 33596,
      "out": 8758,
      "provider": "gemini"
    },
    "iukxuE": {
      "in": 34078,
      "out": 18546,
      "provider": "gemini"
    },
    "MQsurE": {
      "in": 28910,
      "out": 15297,
      "provider": "gemini"
    },
    "DfIw-c": {
      "in": 25888,
      "out": 9851,
      "provider": "gemini"
    },
    "ABmn4M": {
      "in": 43130,
      "out": 20338,
      "provider": "gemini"
    },
    "Kh4TJg": {
      "in": 58763,
      "out": 28407,
      "provider": "gemini"
    },
    "aRfB6I": {
      "in": 60684,
      "out": 19153,
      "provider": "gemini"
    },
    "A1NvKE": {
      "in": 35417,
      "out": 21163,
      "provider": "gemini"
    },
    "y8RaQ0": {
      "in": 37995,
      "out": 18891,
      "provider": "gemini"
    },
    "XFdGso": {
      "in": 36036,
      "out": 22109,
      "provider": "gemini"
    },
    "PNu5Do": {
      "in": 33985,
      "out": 21033,
      "provider": "gemini"
    },
    "DcVJTI": {
      "in": 64087,
      "out": 11083,
      "provider": "gemini"
    },
    "k360TE": {
      "in": 38671,
      "out": 17964,
      "provider": "gemini"
    },
    "iWi-QQ": {
      "in": 116446,
      "out": 26769,
      "provider": "gemini"
    },
    "Fth7mM": {
      "in": 19884,
      "out": 8163,
      "provider": "gemini"
    },
    "m1Snm0": {
      "in": 324518,
      "out": 6203,
      "provider": "gemini"
    },
    "BZ6we0": {
      "in": 13571,
      "out": 6679,
      "provider": "gemini"
    },
    "nLSYa8": {
      "in": 49178,
      "out": 12892,
      "provider": "gemini"
    },
    "CKGwWc": {
      "in": 19719,
      "out": 5974,
      "provider": "gemini"
    },
    "UmQd9E": {
      "in": 21459,
      "out": 10792,
      "provider": "gemini"
    },
    "DaWkoA": {
      "in": 26115,
      "out": 7237,
      "provider": "gemini"
    },
    "sbx90M": {
      "in": 20513,
      "out": 44574,
      "provider": "gemini"
    },
    "DM_aRI": {
      "in": 27717,
      "out": 11987,
      "provider": "gemini"
    },
    "b3lDkg": {
      "in": 39995,
      "out": 11625,
      "provider": "gemini"
    },
    "hXizEI": {
      "in": 40768,
      "out": 10892,
      "provider": "gemini"
    },
    "1JMISc": {
      "in": 32523,
      "out": 21201,
      "provider": "gemini"
    },
    "MFcZ3g": {
      "in": 33168,
      "out": 27381,
      "provider": "gemini"
    },
    "3c8FkE": {
      "in": 16475,
      "out": 6576,
      "provider": "gemini"
    },
    "c2L5tw": {
      "in": 63794,
      "out": 15109,
      "provider": "gemini"
    },
    "OESwxc": {
      "in": 42436,
      "out": 11965,
      "provider": "gemini"
    },
    "gDUW_w": {
      "in": 51006,
      "out": 14220,
      "provider": "gemini"
    },
    "HAFV6E": {
      "in": 29292,
      "out": 9912,
      "provider": "gemini"
    },
    "qjMmhA": {
      "in": 73368,
      "out": 31462,
      "provider": "gemini"
    },
    "W1X_tU": {
      "in": 18218,
      "out": 9626,
      "provider": "gemini"
    },
    "jfw4o0": {
      "in": 7732,
      "out": 6919,
      "provider": "gemini"
    },
    "kcUeag": {
      "in": 6114,
      "out": 3314,
      "provider": "gemini"
    },
    "qVdmiE": {
      "in": 18997,
      "out": 13311,
      "provider": "gemini"
    },
    "ATHON0": {
      "in": 12373,
      "out": 7664,
      "provider": "gemini"
    },
    "fpajkA": {
      "in": 29232,
      "out": 12914,
      "provider": "gemini"
    },
    "2sWdVA": {
      "in": 47699,
      "out": 15362,
      "provider": "gemini"
    },
    "lFwHNI": {
      "in": 81239,
      "out": 22274,
      "provider": "gemini"
    },
    "WN1Q74": {
      "in": 12143,
      "out": 7347,
      "provider": "gemini"
    },
    "bVylvo": {
      "in": 9960,
      "out": 3854,
      "provider": "gemini"
    },
    "3tyX6g": {
      "in": 18518,
      "out": 10769,
      "provider": "gemini"
    },
    "_xlpoE": {
      "in": 31208,
      "out": 2838,
      "provider": "gemini"
    },
    "mKoid4": {
      "in": 174402,
      "out": 7489,
      "provider": "gemini"
    },
    "HloDP8": {
      "in": 15139,
      "out": 2089,
      "provider": "gemini"
    },
    "QMWq28": {
      "in": 10540,
      "out": 5276,
      "provider": "gemini"
    },
    "T7Wg1s": {
      "in": 13779,
      "out": 1959,
      "provider": "gemini"
    },
    "56KMEg": {
      "in": 69239,
      "out": 3143,
      "provider": "gemini"
    },
    "m_ea3E": {
      "in": 8790,
      "out": 3719,
      "provider": "gemini"
    },
    "ZjY6VU": {
      "in": 12938,
      "out": 6058,
      "provider": "gemini"
    },
    "tFUcaM": {
      "in": 9076,
      "out": 2650,
      "provider": "gemini"
    },
    "HiWOgU": {
      "in": 40130,
      "out": 7215,
      "provider": "gemini"
    },
    "KApfbE": {
      "in": 48021,
      "out": 947,
      "provider": "gemini"
    },
    "ZzyaLo": {
      "in": 40479,
      "out": 2459,
      "provider": "gemini"
    },
    "4_5rnQ": {
      "in": 2614,
      "out": 12,
      "provider": "gemini"
    },
    "A0EyyE": {
      "in": 126022,
      "out": 9279,
      "provider": "gemini"
    },
    "C1292w": {
      "in": 10222,
      "out": 400,
      "provider": "gemini"
    },
    "-mY6Y8": {
      "in": 17679,
      "out": 1272,
      "provider": "gemini"
    },
    "bV4v1Y": {
      "in": 9085,
      "out": 1050,
      "provider": "gemini"
    },
    "uRsxKc": {
      "in": 23722,
      "out": 10513,
      "provider": "gemini"
    },
    "Y9e5MA": {
      "in": 231239,
      "out": 2000,
      "provider": "gemini"
    },
    "VsXVRM": {
      "in": 10454,
      "out": 2775,
      "provider": "gemini"
    },
    "R1dLz8": {
      "in": 25266,
      "out": 10672,
      "provider": "gemini"
    },
    "OBYqCQ": {
      "in": 24576,
      "out": 645,
      "provider": "gemini"
    },
    "d5465b": {
      "in": 6412423,
      "out": 107463,
      "provider": "gemini"
    },
    "9sVQWs": {
      "in": 16747,
      "out": 6977,
      "provider": "gemini"
    },
    "0e0fSY": {
      "in": 7183,
      "out": 3835,
      "provider": "gemini"
    },
    "K1xJOQ": {
      "in": 4220,
      "out": 1755,
      "provider": "gemini"
    },
    "nsrZwQ": {
      "in": 7221,
      "out": 492,
      "provider": "gemini"
    },
    "Rw0m6U": {
      "in": 8327,
      "out": 2354,
      "provider": "gemini"
    },
    "pMq2is": {
      "in": 16382,
      "out": 8387,
      "provider": "gemini"
    },
    "oU9Ix8": {
      "in": 6040,
      "out": 7419,
      "provider": "gemini"
    },
    "WAxEkU": {
      "in": 1199,
      "out": 201,
      "provider": "gemini"
    },
    "8rf6S0": {
      "in": 19578,
      "out": 6137,
      "provider": "gemini"
    },
    "ptYooc": {
      "in": 24526,
      "out": 3132,
      "provider": "gemini"
    },
    "KmFFhQ": {
      "in": 5038,
      "out": 1766,
      "provider": "gemini"
    },
    "m8LjaY": {
      "in": 8278,
      "out": 4215,
      "provider": "gemini"
    },
    "74g7X0": {
      "in": 9626,
      "out": 3023,
      "provider": "gemini"
    },
    "QkCNY4": {
      "in": 13440,
      "out": 4701,
      "provider": "gemini"
    },
    "8MTBpQ": {
      "in": 10106,
      "out": 1955,
      "provider": "gemini"
    },
    "yEWTWY": {
      "in": 17503,
      "out": 3157,
      "provider": "gemini"
    },
    "iK1UfA": {
      "in": 32885,
      "out": 4321,
      "provider": "gemini"
    },
    "zUsNxs": {
      "in": 20562,
      "out": 10484,
      "provider": "gemini"
    },
    "qlmsTs": {
      "in": 7417,
      "out": 834,
      "provider": "gemini"
    },
    "pZ7W4E": {
      "in": 5467,
      "out": 6292,
      "provider": "gemini"
    },
    "1wcP10": {
      "in": 40731,
      "out": 13523,
      "provider": "gemini"
    },
    "SpUlGA": {
      "in": 25984,
      "out": 12603,
      "provider": "gemini"
    },
    "HykzBk": {
      "in": 17312,
      "out": 9700,
      "provider": "gemini"
    },
    "h_DJlQ": {
      "in": 5729,
      "out": 5406,
      "provider": "gemini"
    },
    "tmo5Cg": {
      "in": 22983,
      "out": 10522,
      "provider": "gemini"
    },
    "E9cVr4": {
      "in": 4910,
      "out": 2467,
      "provider": "gemini"
    },
    "TqK5yw": {
      "in": 12504,
      "out": 15284,
      "provider": "gemini"
    },
    "mqcLxw": {
      "in": 4980,
      "out": 4852,
      "provider": "gemini"
    },
    "VCK3z8": {
      "in": 19892,
      "out": 8791,
      "provider": "gemini"
    },
    "nqaO7Y": {
      "in": 5700,
      "out": 4407,
      "provider": "gemini"
    },
    "RyST-g": {
      "in": 10600,
      "out": 7998,
      "provider": "gemini"
    },
    "vMwnuU": {
      "in": 5889,
      "out": 5225,
      "provider": "gemini"
    },
    "HGkX9I": {
      "in": 19498,
      "out": 7245,
      "provider": "gemini"
    },
    "Qe76ZE": {
      "in": 16121,
      "out": 11493,
      "provider": "gemini"
    },
    "-eI9xU": {
      "in": 6828,
      "out": 5643,
      "provider": "gemini"
    },
    "RvSlio": {
      "in": 5019,
      "out": 3191,
      "provider": "gemini"
    },
    "3syhXM": {
      "in": 13821,
      "out": 8941,
      "provider": "gemini"
    },
    "D-tkAY": {
      "in": 3347,
      "out": 1523,
      "provider": "gemini"
    },
    "-sBoWM": {
      "in": 7635,
      "out": 1353,
      "provider": "gemini"
    },
    "DIG8mw": {
      "in": 34751,
      "out": 1386,
      "provider": "gemini"
    },
    "xpaJxI": {
      "in": 19963,
      "out": 11759,
      "provider": "gemini"
    },
    "0_RDzo": {
      "in": 13013,
      "out": 7217,
      "provider": "gemini"
    },
    "Kh6vOA": {
      "in": 27808,
      "out": 6214,
      "provider": "gemini"
    },
    "-JhEkA": {
      "in": 214877,
      "out": 7189,
      "provider": "gemini"
    },
    "PMX0Os": {
      "in": 11332,
      "out": 4201,
      "provider": "gemini"
    },
    "6Wcwe8": {
      "in": 4824,
      "out": 4202,
      "provider": "gemini"
    },
    "mj0PL4": {
      "in": 16575,
      "out": 10128,
      "provider": "gemini"
    },
    "ZsD4UU": {
      "in": 5315,
      "out": 5422,
      "provider": "gemini"
    },
    "q-t4Og": {
      "in": 9310,
      "out": 3501,
      "provider": "gemini"
    },
    "GOvAVU": {
      "in": 5096,
      "out": 5851,
      "provider": "gemini"
    },
    "gGhO7s": {
      "in": 10611,
      "out": 4627,
      "provider": "gemini"
    },
    "2klsgE": {
      "in": 18779,
      "out": 15814,
      "provider": "gemini"
    },
    "1edEEw": {
      "in": 7069,
      "out": 6554,
      "provider": "gemini"
    },
    "HxDXfw": {
      "in": 12367,
      "out": 8371,
      "provider": "gemini"
    },
    "woTmGU": {
      "in": 9516,
      "out": 3359,
      "provider": "gemini"
    },
    "P8f1o4": {
      "in": 10022,
      "out": 5018,
      "provider": "gemini"
    },
    "KeEUYY": {
      "in": 24691,
      "out": 1383,
      "provider": "gemini"
    },
    "pkN894": {
      "in": 14864,
      "out": 7467,
      "provider": "gemini"
    },
    "MLtZZs": {
      "in": 10179,
      "out": 4104,
      "provider": "gemini"
    },
    "WtH1KU": {
      "in": 3533,
      "out": 2280,
      "provider": "gemini"
    },
    "nirKKw": {
      "in": 8562,
      "out": 3952,
      "provider": "gemini"
    },
    "TbOGY8": {
      "in": 7223,
      "out": 7359,
      "provider": "gemini"
    },
    "K-DB0M": {
      "in": 10304,
      "out": 5063,
      "provider": "gemini"
    },
    "PQ6Kls": {
      "in": 7791,
      "out": 7198,
      "provider": "gemini"
    },
    "5h1PIg": {
      "in": 10925,
      "out": 8770,
      "provider": "gemini"
    },
    "CbBw-Q": {
      "in": 9868,
      "out": 8377,
      "provider": "gemini"
    },
    "xX3f0M": {
      "in": 9570,
      "out": 3425,
      "provider": "gemini"
    },
    "HzOyv8": {
      "in": 6126,
      "out": 7819,
      "provider": "gemini"
    },
    "SrOyEI": {
      "in": 7170,
      "out": 5856,
      "provider": "gemini"
    },
    "voDRJ0": {
      "in": 2300,
      "out": 2399,
      "provider": "gemini"
    },
    "ifA_gA": {
      "in": 97809,
      "out": 6260,
      "provider": "gemini"
    },
    "EJXabU": {
      "in": 1113,
      "out": 1204,
      "provider": "gemini"
    },
    "u9dIGY": {
      "in": 6895,
      "out": 6432,
      "provider": "gemini"
    },
    "9xPUQw": {
      "in": 3457,
      "out": 2140,
      "provider": "gemini"
    },
    "9S9qHI": {
      "in": 11196,
      "out": 3003,
      "provider": "gemini"
    },
    "ibG0cM": {
      "in": 20224,
      "out": 5466,
      "provider": "gemini"
    },
    "a7OfWI": {
      "in": 85274,
      "out": 67019,
      "provider": "gemini"
    },
    "sz8324": {
      "in": 8956,
      "out": 1752,
      "provider": "gemini"
    },
    "pWnyYs": {
      "in": 15686,
      "out": 3989,
      "provider": "gemini"
    },
    "2P6zGg": {
      "in": 5820,
      "out": 4887,
      "provider": "gemini"
    },
    "bh66UA": {
      "in": 26405,
      "out": 6286,
      "provider": "gemini"
    },
    "S1FYDc": {
      "in": 8483,
      "out": 1505,
      "provider": "gemini"
    },
    "6k1ceg": {
      "in": 10448,
      "out": 4889,
      "provider": "gemini"
    },
    "EEsKcs": {
      "in": 13195,
      "out": 7620,
      "provider": "gemini"
    },
    "o14LnU": {
      "in": 8427,
      "out": 5039,
      "provider": "gemini"
    },
    "4FT3IE": {
      "in": 8229,
      "out": 1229,
      "provider": "gemini"
    },
    "FOTjJY": {
      "in": 137,
      "out": 2814,
      "provider": "gemini"
    }
  }
}
"""
with open("token_usage.json", "w", encoding="utf-8") as f:
    f.write(file_content)

# Charger les données
usage_data = load_token_usage_data("token_usage.json")

# Analyser et afficher
analyze_token_usage(usage_data)
# `analyze_payloads.py` Technical Documentation

## Description
Ce module utilitaire fournit des fonctions pour l'analyse, la validation et l'extraction d'informations à partir de différents types de charges utiles (payloads) de données. Il est conçu pour traiter divers formats tels que JSON, XML et URL-encoded, et peut inclure des fonctionnalités pour identifier des modèles spécifiques, notamment des indicateurs de sécurité.

## Dépendances
*   `json` (module standard pour l'analyse JSON)
*   `xml.etree.ElementTree` (module standard pour l'analyse XML)
*   `urllib.parse` (module standard pour l'analyse des chaînes URL-encoded)
*   `re` (module standard pour les expressions régulières)
*   `typing` (pour les annotations de type)

## Classes & Fonctions

### `parse_json_payload(payload_str: str) -> Optional[Dict[str, Any]]`
Parse une chaîne JSON en un objet Python (dictionnaire ou liste).

#### Arguments
*   `payload_str` (`str`): La chaîne de caractères représentant la charge utile au format JSON.

#### Retours
*   `Optional[Dict[str, Any]]`: Un dictionnaire Python si la chaîne JSON est valide, sinon `None` en cas d'erreur de décodage.

#### Logique interne
La fonction tente de décoder la chaîne `payload_str` en utilisant `json.loads()`. Si la chaîne n'est pas un JSON valide, un `json.JSONDecodeError` est intercepté, et un message d'erreur est enregistré avant de retourner `None`.

---

### `parse_xml_payload(payload_str: str) -> Optional[ET.Element]`
Parse une chaîne XML en un objet `xml.etree.ElementTree.Element`, représentant la racine de l'arbre XML.

#### Arguments
*   `payload_str` (`str`): La chaîne de caractères représentant la charge utile au format XML.

#### Retours
*   `Optional[ET.Element]`: L'élément racine de l'arbre XML si la chaîne est valide, sinon `None` en cas d'erreur de parsing.

#### Logique interne
La fonction utilise `xml.etree.ElementTree.fromstring()` pour analyser la chaîne XML. Si la chaîne n'est pas un XML bien formé, un `xml.etree.ElementTree.ParseError` est intercepté, un message d'erreur est enregistré, et `None` est retourné.

---

### `parse_url_encoded_payload(payload_str: str) -> Dict[str, List[str]]`
Parse une chaîne de requête URL-encoded (par exemple, `key1=value1&key2=value2`) en un dictionnaire de listes.

#### Arguments
*   `payload_str` (`str`): La chaîne de caractères représentant la charge utile au format URL-encoded.

#### Retours
*   `Dict[str, List[str]]`: Un dictionnaire où les clés sont les noms des paramètres et les valeurs sont des listes de leurs occurrences.

#### Logique interne
La fonction utilise `urllib.parse.parse_qs()` pour décomposer la chaîne. Cette fonction gère automatiquement le décodage des URL et la gestion des paramètres multiples avec le même nom.

---

### `identify_xss_patterns(payload: str) -> List[str]`
Recherche des modèles courants d'attaques Cross-Site Scripting (XSS) au sein d'une charge utile textuelle.

#### Arguments
*   `payload` (`str`): La charge utile textuelle à analyser.

#### Retours
*   `List[str]`: Une liste de chaînes de caractères, chacune représentant un modèle XSS identifié. Si aucun modèle n'est trouvé, une liste vide est retournée.

#### Logique interne
La fonction utilise des expressions régulières pour rechercher des motifs connus associés aux attaques XSS, tels que des balises `<script>`, des attributs d'événements JavaScript (`onerror=`, `onload=`), des schémas `javascript:`, etc. Une liste prédéfinie de regex est itérée, et toutes les correspondances trouvées sont collectées.

---

### `validate_payload_schema(payload: Dict[str, Any], schema: Dict[str, Any]) -> bool`
Valide une charge utile (dictionnaire) par rapport à un schéma défini.

#### Arguments
*   `payload` (`Dict[str, Any]`): La charge utile parsée sous forme de dictionnaire.
*   `schema` (`Dict[str, Any]`): Le schéma attendu, décrivant la structure et les types de données attendus.

#### Retours
*   `bool`: `True` si la charge utile correspond au schéma, `False` sinon.

#### Logique interne
Cette fonction effectue une validation de base en vérifiant la présence des clés requises (`"required": True`) et la correspondance des types de données spécifiés dans le schéma pour les clés présentes dans la charge utile. Elle supporte des types simples comme `str`, `int`, `bool`, `list`, `dict`. Pour une validation plus complexe (par exemple, expressions régulières pour les chaînes, plages de valeurs), une bibliothèque externe comme `jsonschema` serait recommandée dans une implémentation réelle.

---

### `normalize_payload(payload_data: Any) -> str`
Normalise une charge utile de données (dictionnaire, liste, chaîne) en une représentation de chaîne canonique, généralement pour la comparaison ou le hachage.

#### Arguments
*   `payload_data` (`Any`): La charge utile, qui peut être un dictionnaire, une liste, une chaîne ou un autre type de données.

#### Retours
*   `str`: Une représentation de chaîne normalisée de la charge utile.

#### Logique interne
Si `payload_data` est un dictionnaire ou une liste, il est converti en une chaîne JSON triée lexicographiquement pour garantir une représentation cohérente. Les chaînes sont retournées telles quelles. D'autres types de données sont convertis en leur représentation textuelle par défaut.

---

## Exemple d'usage

```python
import json
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional

# (Imaginez que les fonctions ci-dessus sont définies ici ou importées d'un module)

def parse_json_payload(payload_str: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(payload_str)
    except json.JSONDecodeError:
        print(f"Erreur: Le payload n'est pas un JSON valide: {payload_str}")
        return None

def parse_xml_payload(payload_str: str) -> Optional[ET.Element]:
    try:
        return ET.fromstring(payload_str)
    except ET.ParseError:
        print(f"Erreur: Le payload n'est pas un XML valide: {payload_str}")
        return None

def parse_url_encoded_payload(payload_str: str) -> Dict[str, List[str]]:
    from urllib.parse import parse_qs
    return parse_qs(payload_str)

def identify_xss_patterns(payload: str) -> List[str]:
    import re
    xss_patterns = [
        r"<script.*?>",
        r"on[a-zA-Z]+=",
        r"javascript:",
        r"&#x?[0-9a-fA-F]+;" # HTML entities
    ]
    found_patterns = []
    for pattern in xss_patterns:
        matches = re.findall(pattern, payload, re.IGNORECASE)
        if matches:
            found_patterns.extend(list(set(matches))) # Use set to avoid duplicates
    return found_patterns

def validate_payload_schema(payload: Dict[str, Any], schema: Dict[str, Any]) -> bool:
    for key, props in schema.items():
        if props.get("required") and key not in payload:
            print(f"Validation Error: La clé '{key}' est requise mais manquante.")
            return False
        if key in payload:
            expected_type = props.get("type")
            if expected_type and not isinstance(payload[key], expected_type):
                print(f"Validation Error: La clé '{key}' attend le type '{expected_type.__name__}' mais a reçu '{type(payload[key]).__name__}'.")
                return False
    return True

def normalize_payload(payload_data: Any) -> str:
    if isinstance(payload_data, (dict, list)):
        return json.dumps(payload_data, sort_keys=True, separators=(',', ':'))
    return str(payload_data)

# --- Exemples d'utilisation ---

# 1. Parsing JSON
json_payload = '{"name": "Alice", "age": 30, "city": "New York"}'
parsed_json = parse_json_payload(json_payload)
if parsed_json:
    print(f"JSON Parsé: {parsed_json}")
    print(f"Nom: {parsed_json.get('name')}")

invalid_json = '{"name": "Bob", "age":'
parse_json_payload(invalid_json)

# 2. Parsing XML
xml_payload = '<user><name>Charlie</name><email>charlie@example.com</email></user>'
parsed_xml = parse_xml_payload(xml_payload)
if parsed_xml:
    print(f"XML Parsé (nom de la racine): {parsed_xml.tag}")
    print(f"Nom de l'utilisateur: {parsed_xml.find('name').text}")

# 3. Parsing URL-encoded
url_payload = 'param1=value1&param2=value2&param1=value3'
parsed_url = parse_url_encoded_payload(url_payload)
print(f"URL-encoded Parsé: {parsed_url}")

# 4. Identification de patterns XSS
xss_test_payload = "<script>alert(1)</script> <img src=x onerror=alert(2)> javascript:void(0)"
xss_found = identify_xss_patterns(xss_test_payload)
print(f"Patterns XSS trouvés: {xss_found}")

clean_payload = "This is a clean text without malicious scripts."
print(f"Patterns XSS trouvés (clean): {identify_xss_patterns(clean_payload)}")

# 5. Validation de schéma
user_schema = {
    "name": {"type": str, "required": True},
    "age": {"type": int, "required": False},
    "email": {"type": str, "required": True}
}

valid_user_payload = {"name": "David", "age": 25, "email": "david@example.com"}
invalid_user_payload_missing_key = {"name": "Eve", "age": 40}
invalid_user_payload_wrong_type = {"name": "Frank", "age": "trente", "email": "frank@example.com"}

print(f"Validation de payload valide: {validate_payload_schema(valid_user_payload, user_schema)}")
print(f"Validation de payload avec clé manquante: {validate_payload_schema(invalid_user_payload_missing_key, user_schema)}")
print(f"Validation de payload avec type incorrect: {validate_payload_schema(invalid_user_payload_wrong_type, user_schema)}")

# 6. Normalisation de payload
payload_dict1 = {"b": 2, "a": 1}
payload_dict2 = {"a": 1, "b": 2}
payload_list = [3, 1, 2]

normalized1 = normalize_payload(payload_dict1)
normalized2 = normalize_payload(payload_dict2)
normalized_list = normalize_payload(payload_list)

print(f"Payload dict1 normalisé: {normalized1}")
print(f"Payload dict2 normalisé: {normalized2}")
print(f"Les payloads dict1 et dict2 sont égaux après normalisation: {normalized1 == normalized2}")
print(f"Payload list normalisé: {normalized_list}")
print(f"Chaîne normale normalisée: {normalize_payload('hello')}")
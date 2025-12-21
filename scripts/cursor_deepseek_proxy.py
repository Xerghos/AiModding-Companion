from flask import Flask, request, Response, stream_with_context
import requests
import json
import sys

app = Flask(__name__)

# --- CONFIGURATION ---
# Remplacez par votre vraie clé API DeepSeek
DEEPSEEK_API_KEY = "sk-0010b10663bc4b2eaebb63fb571feb75" 
# L'endpoint officiel V3.2
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"
# Le modèle cible (V3.2 Thinking)
TARGET_MODEL = "deepseek-reasoner" 

@app.route('/v1/chat/completions', methods=['POST'])
def proxy():
    try:
        incoming_data = request.json
        messages = incoming_data.get('messages',)

        # --- FIX 1: Fusion des messages User consécutifs ---
        # DeepSeek rejette "User, User". Cursor envoie souvent "User(Context), User(Prompt)".
        # On les fusionne en un seul message.
        merged_messages = []
        if messages:
            current_msg = messages
            for i in range(1, len(messages)):
                next_msg = messages[i]
                if current_msg['role'] == 'user' and next_msg['role'] == 'user':
                    # Fusion du contenu
                    current_msg['content'] += "\n\n" + next_msg['content']
                else:
                    merged_messages.append(current_msg)
                    current_msg = next_msg
            merged_messages.append(current_msg)
        
        # Préparation de la requête vers DeepSeek
        payload = {
            "model": TARGET_MODEL,
            "messages": merged_messages,
            "stream": True,
            "temperature": 0.6 # V3.2 tolère la température, contrairement à R1
        }

        # Copier les paramètres max_tokens s'ils existent
        if 'max_tokens' in incoming_data:
            payload['max_tokens'] = incoming_data['max_tokens']

        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        # --- FIX 2: Gestion du Streaming et Affichage de la Pensée ---
        def generate():
            try:
                with requests.post(DEEPSEEK_URL, json=payload, headers=headers, stream=True) as resp:
                    if resp.status_code!= 200:
                        yield f"data: {json.dumps({'error': resp.text})}\n\n"
                        return

                    for line in resp.iter_lines():
                        if line:
                            decoded_line = line.decode('utf-8')
                            if decoded_line.startswith("data: ") and decoded_line!= "data:":
                                try:
                                    chunk = json.loads(decoded_line[6:])
                                    delta = chunk['choices'].get('delta', {})
                                    
                                    # Gestion du contenu de raisonnement (Thinking Process)
                                    # On le transforme en texte italique pour qu'il soit visible dans Cursor
                                    if 'reasoning_content' in delta and delta['reasoning_content']:
                                        reasoning_text = delta['reasoning_content']
                                        # On simule un contenu standard pour tromper Cursor
                                        new_chunk = {
                                            "id": chunk['id'],
                                            "object": "chat.completion.chunk",
                                            "created": chunk['created'],
                                            "model": "GPT-5 Nano", # On ment pour la compatibilité UI
                                            "choices": [{
                                                "index": 0,
                                                "delta": {"content": f"_{reasoning_text}_ "}, # Italique pour la pensée
                                                "finish_reason": None
                                            }]
                                        }
                                        yield f"data: {json.dumps(new_chunk)}\n\n"
                                    
                                    # Gestion du contenu final (Le code/réponse)
                                    elif 'content' in delta and delta['content']:
                                        # On laisse passer tel quel
                                        yield f"{decoded_line}\n"
                                        
                                except json.JSONDecodeError:
                                    continue
                            elif decoded_line == "data:":
                                yield "data:\n\n"
            except Exception as e:
                error_msg = {"error": {"message": str(e)}}
                yield f"data: {json.dumps(error_msg)}\n\n"

        return Response(stream_with_context(generate()), content_type='text/event-stream')

    except Exception as e:
        return Response(json.dumps({"error": str(e)}), status=500, mimetype='application/json')

if __name__ == '__main__':
    print(f"🚀 Proxy DeepSeek V3.2 démarré sur http://127.0.0.1:5000")
    print(f"Cible API: {TARGET_MODEL}")
    app.run(port=5000, debug=True)
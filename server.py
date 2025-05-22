import asyncio
import websockets
import json
import logging


# Config du logging pour voir ce qui se passe
logging.basicConfig(level=logging.INFO)

# Ensemble pour garder une trace de tous les clients connectés et de leur nom d'utilisateur
# Clé: objet websocket, valeur: nom d'user
CONNECTED_CLIENTS = {}

async def register(websocket, username):
    """Enregistre un nouveau client avec son nom d'user"""
    CONNECTED_CLIENTS[websocket] = username
    logging.info(f"'{username}' ({websocket.remote_address}) s'est connecté.")
    logging.info(f"Clients connectés: {len(CONNECTED_CLIENTS)} ({', '.join(CONNECTED_CLIENTS.values())})")

async def unregister(websocket):
    """Désenregistre un client"""
    username = CONNECTED_CLIENTS.pop(websocket, "Un utilisateur inconnu")
    CONNECTED_CLIENTS.remove(websocket)
    logging.info(f"'{username}' ({websocket.remote_address}) s'est déconnecté.")   
    logging.info(f"Clients connectés: {len(CONNECTED_CLIENTS)} ({', '.join(CONNECTED_CLIENTS.values())})")
    # Notifier tout le monde que quelqu'un est parti
    leave_message = json.dumps({"type": "system", "text": f"'{username}' a quitté le chat."})
    await broadcast_message(leave_message)

async def broadcast_message(message_json_string, sender_websocket=None):
    """Diffuse un message (chaîne JSON) à tous les clients connectés"""
    if CONNECTED_CLIENTS:
        tasks = [client.send(message_json_string) for client in CONNECTED_CLIENTS]
        await asyncio.gather(*tasks) # Exécute toutes les tâches d'envoi en parallèle

async def chat_handler(websocket, path):
    """Gère la connexion WebSocket pour un client."""
    # La première action du client devrait être d'envoyer son nom d'utilisateur
    # Pour simplifier, on attend un premier message de type "join"
  
    # On ne l'enregistre pas tant qu'on n'a pas son nom
    current_username = None

    try:
        async for message_str in websocket:
            logging.info(f"Message reçu de {websocket.remote_address}: {message_str}")
            try:
                data = json.loads(message_str)
                message_type = data.get("type")
                user = data.get("user") # Le nom d'utilisateur envoyé par le client

                if message_type == "join" and user:
                    if websocket not in CONNECTED_CLIENTS: # S'il n'est pas déjà enregistré
                        current_username = user
                        await register(websocket, current_username)
                    # Ne rien faire de plus avec le message "join" ici, register s'en occupe
                    continue # Passe au message suivant

                elif message_type == "leave" and user:
                    # Le client peut explicitement envoyer un "leave" avant de se déconnecter
                    # unregister sera appelé dans le finally de toute façon
                    pass

                elif message_type == "message" and user and websocket in CONNECTED_CLIENTS:
                    # S'assure que l'utilisateur est bien celui enregistré pour ce websocket
                    # et qu'il a bien un message à envoyer
                    if CONNECTED_CLIENTS[websocket] == user and data.get("text"):
                        # On reformate le message pour inclure l'expéditeur
                        # et on le diffuse
                        broadcast_data = {
                            "type": "message",
                            "user": user, # Le nom de l'utilisateur qui a envoyé
                            "text": data["text"]
                        }
                        await broadcast_message(json.dumps(broadcast_data))
                    else:
                        logging.warning(f"Message invalide ou tentative d'usurpation de {user} par {websocket.remote_address}")
                else:
                    logging.warning(f"Message non géré ou mal formaté de {websocket.remote_address}: {data}")

            except json.JSONDecodeError:
                logging.error(f"Message non JSON reçu de {websocket.remote_address}: {message_str}")
                # Optionnel: envoyer une erreur au client
                await websocket.send(json.dumps({"type": "error", "text": "Message mal formaté."}))
            except Exception as e:
                logging.error(f"Erreur lors du traitement du message de {websocket.remote_address}: {e}")


    except websockets.exceptions.ConnectionClosedOK:
        logging.info(f"Connexion fermée proprement par {current_username or websocket.remote_address}")
    except websockets.exceptions.ConnectionClosedError as e:
        logging.error(f"Connexion fermée avec erreur par {current_username or websocket.remote_address}: {e}")
    finally:
        if websocket in CONNECTED_CLIENTS: # S'assurer qu'il était enregistré
            await unregister(websocket)
            
async def main():
    host = "localhost"
    port = 8765
    logging.info(f"Serveur WebSocket démarré sur ws://{host}:{port}")
    async with websockets.serve(chat_handler, host, port, ping_interval=20, ping_timeout=20):
        await asyncio.Future() # Maintient le serveur en fonctionnement indéfiniment

if __name__ == "__main__":
    asyncio.run(main())


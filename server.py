"""
Serveur de chat WebSocket avec MongoDB
-------------------------------------

Ce serveur permet aux utilisateurs de se connecter via WebSocket,
de rejoindre des salles de discussion et d'échanger des messages.
Les messages et les informations sur les utilisateurs sont stockés dans MongoDB.

Fonctionnalités:
- Connexion/déconnexion des utilisateurs
- Création et gestion de salles de discussion
- Historique des messages par salle
- Stockage persistant avec MongoDB

Dépendances:
- websockets
- motor (client MongoDB asynchrone)
- asyncio
"""

import asyncio
import websockets
import json
import logging
import motor.motor_asyncio
import signal


# Config du logging pour voir ce qui se passe
logging.basicConfig(level=logging.INFO)

# Connexion à MongoDB
client = motor.motor_asyncio.AsyncIOMotorClient('mongodb://localhost:27017')
db = client.chat_db  # Base de données
messages_collection = db.messages  # Collection pour les messages
users_collection = db.users  # Collection pour les utilisateurs
rooms_collection = db.rooms  # Collection pour les salons

async def get_or_create_user(username):
    """Récupère ou crée un utilisateur dans la base de données"""
    user = await users_collection.find_one({"username": username})
    if not user:
        user = {
            "username": username,
            "created_at": asyncio.datetime.datetime.now(),
            "last_seen": asyncio.datetime.datetime.now()
        }
        await users_collection.insert_one(user)
    else:
        # Mettre à jour last_seen
        await users_collection.update_one(
            {"username": username},
            {"$set": {"last_seen": asyncio.datetime.datetime.now()}}
        )
    return user

# Ensemble pour garder une trace de tous les clients connectés et de leur nom d'utilisateur
CONNECTED_CLIENTS = {}

async def register(websocket, username):
    """Enregistre un nouveau client avec son nom d'user et lui envoie l'historique"""

    # Enregistrer l'utilisateur dans la base de données
    user = await get_or_create_user(username)

    CONNECTED_CLIENTS[websocket] = username
    logging.info(f"'{username}' ({websocket.remote_address}) s'est connecté.")
    logging.info(f"Clients connectés: {len(CONNECTED_CLIENTS)} ({', '.join(CONNECTED_CLIENTS.values())})")

    # Notifier tout le monde qu'un nouvel utilisateur est arrivé
    join_message = json.dumps({"type": "system", "text": f"'{username}' a rejoint le chat."})
    await broadcast_message(join_message)

    # Envoyer l'historique des messages au nouveau client
    history = await get_message_history()
    for msg in history:
        history_message = json.dumps({
            "type": "message",
            "user": msg["user"],
            "text": msg["text"],
            "timestamp": msg["timestamp"].isoformat()
        })
        await websocket.send(history_message)


async def unregister(websocket):
    """Désenregistre un client de toutes les salles et du chat global"""
    username = CONNECTED_CLIENTS.pop(websocket, "Un utilisateur inconnu")
    
    # Supprimer l'utilisateur de toutes les salles
    for room_id, clients in list(ROOM_CLIENTS.items()):
        if websocket in clients:
            del clients[websocket]
            # Notifier les autres utilisateurs de la salle
            room_message = json.dumps({
                "type": "system",
                "room": room_id,
                "text": f"'{username}' a quitté la salle '{room_id}'."
            })
            await broadcast_to_room(room_message, room_id)
            
            # Si la salle est vide, la supprimer de la mémoire
            if not clients:
                del ROOM_CLIENTS[room_id]
    
    logging.info(f"'{username}' ({websocket.remote_address}) s'est déconnecté.")   
    logging.info(f"Clients connectés: {len(CONNECTED_CLIENTS)} ({', '.join(CONNECTED_CLIENTS.values())})")
    
    # Notifier tout le monde que quelqu'un est parti
    leave_message = json.dumps({"type": "system", "text": f"'{username}' a quitté le chat."})
    await broadcast_message(leave_message)

async def broadcast_message(message_json_string, sender_websocket=None):
    """Diffuse un message (chaîne JSON) à tous les clients connectés et le sauvegarde"""
    if CONNECTED_CLIENTS:
        # Envoyer le message à tous les clients
        tasks = [client.send(message_json_string) for client in CONNECTED_CLIENTS]
        await asyncio.gather(*tasks) # Exécute toutes les tâches d'envoi en parallèle

        # Sauvegarder le message dans MongoDB
        message_data = json.loads(message_json_string)
        if message_data.get("type") == "message":  # Ne sauvegarder que les messages utilisateur
            await messages_collection.insert_one({
                "user": message_data.get("user"),
                "text": message_data.get("text"),
                "timestamp": asyncio.datetime.datetime.now()
            })

async def get_message_history(limit=50):
    """Récupère les derniers messages de la base de données"""
    try:
        cursor = messages_collection.find().sort("timestamp", -1).limit(limit)
        messages = await cursor.to_list(length=limit)
        messages.reverse()
        return messages
    except Exception as e:
        logging.error(f"Erreur lors de la récupération de l'historique: {e}")
        return []

# Ajouter cette fonction d'aide pour gérer les erreurs MongoDB
async def safe_db_operation(operation, fallback_value=None):
    """Exécute une opération MongoDB avec gestion d'erreur"""
    try:
        return await operation
    except Exception as e:
        logging.error(f"Erreur MongoDB: {e}")
        return fallback_value

async def get_message_history(limit=50):
    """Récupère les derniers messages de la base de données"""
    return await safe_db_operation(
        messages_collection.find().sort("timestamp", -1).limit(limit).to_list(length=limit),
        fallback_value=[]
    )

async def get_message_history(limit=50):
    """Récupère les derniers messages de la base de données"""
    try:
        cursor = messages_collection.find().sort("timestamp", -1).limit(limit)
        messages = await cursor.to_list(length=limit)
        messages.reverse()
        return messages
    except Exception as e:
        logging.error(f"Erreur lors de la récupération de l'historique: {e}")
        return []



async def join_room(websocket, username, room_id="general"):
    """Fait rejoindre une salle à un utilisateur"""
    # Vérifier si la salle existe, sinon la créer
    if room_id not in ROOM_CLIENTS:
        ROOM_CLIENTS[room_id] = {}
        # Vérifier/créer la salle dans MongoDB
        room = await rooms_collection.find_one({"room_id": room_id})
        if not room:
            await rooms_collection.insert_one({"room_id": room_id, "created_at": asyncio.datetime.datetime.now(), "created_by": username })
        # Ajouter l'utilisateur à la salle
        ROOM_CLIENTS[room_id][websocket] = username

        # Notifier les autres utilisateurs de la salle
        room_message = json.dumps({
            "type": "system",
            "room": room_id,
            "text": f"'{username}' a rejoint la salle '{room_id}'."
        })
        await broadcast_to_room(room_message, room_id)

        # Envoyer l'historique des messages de la salle
        history = await get_room_message_history(room_id)
        for msg in history:
            history_message = json.dumps({
                "type": "message",
                "room": room_id,
                "user": msg["user"],
                "text": msg["text"],
                "timestamp": msg["timestamp"].isoformat()
            })
            await websocket.send(history_message)


async def leave_room(websocket, username, room_id):
    """Fait quitter une salle à un utilisateur"""
    if room_id in ROOM_CLIENTS and websocket in ROOM_CLIENTS[room_id]:
        # Supprimer l'utilisateur de la salle
        del ROOM_CLIENTS[room_id][websocket]
        
        # Notifier les autres utilisateurs de la salle
        room_message = json.dumps({
            "type": "system",
            "room": room_id,
            "text": f"'{username}' a quitté la salle '{room_id}'."
        })
        await broadcast_to_room(room_message, room_id)
        
        # Si la salle est vide, la supprimer de la mémoire
        if not ROOM_CLIENTS[room_id]:
            del ROOM_CLIENTS[room_id]


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
                room_id = data.get("room", "general") # Salle par défaut si non spécifiée

                if message_type == "join" and user:
                    if websocket not in CONNECTED_CLIENTS: # S'il n'est pas déjà enregistré
                        current_username = user
                        await register(websocket, current_username)
                        # Rejoindre la salle par défaut
                        await join_room(websocket, current_username)
                    continue # Passe au message suivant

                elif message_type == "join_room" and user and data.get("room"):
                    # Rejoindre une salle spécifique
                    if websocket in CONNECTED_CLIENTS and CONNECTED_CLIENTS[websocket] == user:
                        await join_room(websocket, user, data.get("room"))
                    continue

                elif message_type == "message" and user and websocket in CONNECTED_CLIENTS:
                    # S'assure que l'utilisateur est bien celui enregistré pour ce websocket
                    if CONNECTED_CLIENTS[websocket] == user and data.get("text"):
                        # Vérifier si le message est destiné à une salle spécifique
                        if data.get("room"):
                            # Message pour une salle spécifique
                            broadcast_data = {
                                "type": "message",
                                "room": data.get("room"),
                                "user": user,
                                "text": data["text"]
                            }
                            await broadcast_to_room(json.dumps(broadcast_data), data.get("room"))
                        else:
                            # Message global (pour tous les clients)
                            broadcast_data = {
                                "type": "message",
                                "user": user,
                                "text": data["text"]
                            }
                            await broadcast_message(json.dumps(broadcast_data))
                    else:
                        logging.warning(f"Message invalide ou tentative d'usurpation de {user} par {websocket.remote_address}")
                elif message_type == "get_rooms" and user and websocket in CONNECTED_CLIENTS:
                    # Envoyer la liste des salles disponibles
                    if CONNECTED_CLIENTS[websocket] == user:
                        await send_room_list(websocket)
                    continue
                else:
                    logging.warning(f"Message non géré ou mal formaté de {websocket.remote_address}: {data}")

            except json.JSONDecodeError:
                logging.error(f"Message non JSON reçu de {websocket.remote_address}: {message_str}")
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


async def broadcast_to_room(message_json_string, room_id="general", sender_websocket=None):
    """Diffuse un message à tous les clients d'une salle et le sauvegarde"""
    if room_id in ROOM_CLIENTS and ROOM_CLIENTS[room_id]:
        # Envoyer le message à tous les clients de la salle
        tasks = [client.send(message_json_string) for client in ROOM_CLIENTS[room_id]]
        await asyncio.gather(*tasks)
        
        # Sauvegarder le message dans MongoDB
        message_data = json.loads(message_json_string)
        if message_data.get("type") == "message":
            await messages_collection.insert_one({
                "room": room_id,
                "user": message_data.get("user"),
                "text": message_data.get("text"),
                "timestamp": asyncio.datetime.datetime.now()
            })

async def get_room_message_history(room_id="general", limit=50):
    """Récupère les derniers messages d'une salle"""
    cursor = messages_collection.find({"room": room_id}).sort("timestamp", -1).limit(limit)
    messages = await cursor.to_list(length=limit)
    messages.reverse()
    return messages

async def get_available_rooms():
    """Récupère la liste des salles disponibles"""
    cursor = rooms_collection.find({}, {"room_id": 1, "_id": 0})
    rooms = await cursor.to_list(length=100)
    return [room["room_id"] for room in rooms]

async def send_room_list(websocket):
    """Envoie la liste des salles disponibles à un client"""
    rooms = await get_available_rooms()
    room_list_message = json.dumps({
        "type": "room_list",
        "rooms": rooms
    })
    await websocket.send(room_list_message)

async def check_mongodb_connection():
    """Vérifie la connexion à MongoDB"""
    try:
        # Ping the database
        await client.admin.command('ping')
        logging.info("Connexion à MongoDB établie avec succès")
        return True
    except Exception as e:
        logging.error(f"Impossible de se connecter à MongoDB: {e}")
        return False

async def setup_mongodb_indices():
    """Configure les indices MongoDB pour de meilleures performances"""
    try:
        # Indice sur les messages pour accélérer les requêtes par salle et timestamp
        await messages_collection.create_index([("room", 1), ("timestamp", -1)])
        # Indice sur les utilisateurs pour accélérer les recherches par nom
        await users_collection.create_index([("username", 1)], unique=True)
        # Indice sur les salles pour accélérer les recherches par ID
        await rooms_collection.create_index([("room_id", 1)], unique=True)
        logging.info("Indices MongoDB configurés avec succès")
    except Exception as e:
        logging.error(f"Erreur lors de la configuration des indices MongoDB: {e}")

# Fonction pour fermer proprement la connexion MongoDB
async def cleanup():
    """Ferme proprement les connexions"""
    client.close()
    logging.info("Connexion MongoDB fermée")


def signal_handler():
    """Gère les signaux d'arrêt"""
    logging.info("Signal d'arrêt reçu, nettoyage en cours...")
    asyncio.create_task(cleanup())

async def main():
    host = "localhost"
    port = 8765
    
    # Vérifier la connexion MongoDB
    if not await check_mongodb_connection():
        logging.error("Impossible de démarrer le serveur sans connexion MongoDB")
        return
    
    # Configurer les indices MongoDB
    await setup_mongodb_indices()
    
    # Configurer les gestionnaires de signal
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(sig, signal_handler)
    
    logging.info(f"Serveur WebSocket démarré sur ws://{host}:{port}")
    async with websockets.serve(chat_handler, host, port, ping_interval=20, ping_timeout=20):
        await asyncio.Future()  # Maintient le serveur en fonctionnement indéfiniment

if __name__ == "__main__":
    asyncio.run(main())

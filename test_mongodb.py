import asyncio
import motor.motor_asyncio
import datetime
import logging

logging.basicConfig(level=logging.INFO)

async def test_mongodb():
    # Connexion à MongoDB
    client = motor.motor_asyncio.AsyncIOMotorClient('mongodb+srv://porezguillaumegp:61MYljsKjEZMpAjf@chatsock.anbcpyh.mongodb.net/', 
                                                  serverSelectionTimeoutMS=5000)
    db = client.chat_db
    messages = db.messages
    
    # Test de ping
    try:
        await client.admin.command('ping')
        logging.info("Connexion à MongoDB établie avec succès")
    except Exception as e:
        logging.error(f"Impossible de se connecter à MongoDB: {e}")
        return
    
    # Test d'écriture
    try:
        result = await messages.insert_one({
            "user": "test_user",
            "text": "Test message",
            "timestamp": datetime.datetime.now(),
            "room": "test_room"
        })
        logging.info(f"Message de test sauvegardé avec ID: {result.inserted_id}")
    except Exception as e:
        logging.error(f"Erreur lors de l'écriture dans MongoDB: {e}")
    
    # Test de lecture
    try:
        cursor = messages.find({"user": "test_user"})
        docs = await cursor.to_list(length=10)
        logging.info(f"Messages trouvés: {len(docs)}")
        for doc in docs:
            logging.info(f"Message: {doc}")
    except Exception as e:
        logging.error(f"Erreur lors de la lecture depuis MongoDB: {e}")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(test_mongodb())
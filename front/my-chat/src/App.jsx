import React, { useState, useEffect, useRef } from 'react'
import './App.css'

function App() {
  const [messages, setMessages] = useState([])
  const [inputValue, setInputValue] = useState('')
  const [userName, setUserName] = useState('') // pour le nom d'utilisateur
  const [isUserNameSet, setIsUserNameSet] = useState(false) // pour savoir si le nom d'utilisateur est défini
  const socketRef = useRef(null) // pour la référence du socket
  const [rooms, setRooms] = useState([]);
  const [currentRoom, setCurrentRoom] = useState("general");
  const [newRoomName, setNewRoomName] = useState("");

  // Se connecter au serveur WebSocket au montage du composant
  useEffect(() => {
    if (!isUserNameSet) {
      return
    }

    // Créer une nouvelle connexion WebSocket
    socketRef.current = new WebSocket('ws://localhost:8765');
    const socket = socketRef.current;

    socket.onopen = () => {
      console.log('WebSocket connecté');
      setMessages(prevMessages => [...prevMessages, { type: 'system', text: 'Connecté au serveur de chat'}]);
      // Envoyer le nom d'utilisateur au serveur
      socket.send(JSON.stringify({ type: 'join', user: userName }));
      // Demander la liste des salles
      socket.send(JSON.stringify({ type: 'get_rooms', user: userName }));
    }

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data);
      console.log('Message reçu:', data);
      
      if (data.type === 'room_list') {
        setRooms(data.rooms);
      } else if (data.type === 'message' || data.type === 'system') {
        // Ne pas afficher les messages d'autres salles
        if (!data.room || data.room === currentRoom) {
          setMessages(prevMessages => [...prevMessages, data]);
        }
      }
    }

    socket.onclose = (event) => {
      console.log('WebSocket déconnecté');
      if (event.wasClean) {
        setMessages(prevMessages => [ ...prevMessages, { type: 'system', text: `Déconnecté proprement. Code: ${event.code}` }])
      } else {
        setMessages(prevMessages => [ ...prevMessages, { type: 'system', text: `Connexion interrompue. Code: ${event.code}` }])
      }
    }
    
    socket.onerror = (error) => {
      console.error('Erreur WebSocket: ', error);
      setMessages(prevMessages => [ ...prevMessages, { type: 'system', text: `erreur WebSocket.` }])
    }

    // Nettoyage: fermer la connexion websocket quand le composant est démonté
    // ou quand isUserNameSet change
    return () => {
      if (socket) {
        // Envoi d'un message de "leave" avant de fermer
        socket.send(JSON.stringify({ type: 'leave', user: userName}))
        socket.close()
        console.log('Connexion WebSocket fermée au nettoyage');
        
      }
    }
  }, [isUserNameSet, userName]) // se ré-exécute si isUserNameSet ou userName change

  const handleSendMessage = () => {
    if (inputValue.trim() && socketRef.current) {
      socketRef.current.send(JSON.stringify({
        type: 'message',
        user: userName,
        room: currentRoom,
        text: inputValue
      }));
      setInputValue('');
    }
  };

  const handleSetUserName = () => {
    if (userName.trim()) {
      setIsUserNameSet(true);
    }
  };

  if (!isUserNameSet) {
    return (
      <div className='username-container'>
        <h1>Entrez votre pseudo</h1>
        <input type="text" value={userName} onChange={(e) => setUserName(e.target.value)} placeholder='Votre pseudo' onKeyDown={(e) => e.key === 'Enter' && handleSetUserName()} />
        <button onClick={handleSetUserName}>Rejoindre le chat</button>
      </div>
    )
  }

  const handleJoinRoom = (roomId) => {
    socket.send(JSON.stringify({
      type: 'join_room',
      user: userName,
      room: roomId
    }));
    setCurrentRoom(roomId);
    setMessages([]); // Vider les messages pour la nouvelle salle
  }

  const handleCreateRoom = () => {
    if (newRoomName.trim()) {
      handleJoinRoom(newRoomName.trim());
      setNewRoomName("");
    }
  }

  return (
    <div className='App'>
      <h1>Chat & WebSockets</h1>
      <div className='room-section'>
        <h3>Salle actuelle: {currentRoom}</h3>
        <div className='room-list'>
          {rooms.map(room => (
            <button 
              key={room} 
              onClick={() => handleJoinRoom(room)}
              className={room === currentRoom ? 'active' : ''}
            >
              {room}
            </button>
          ))}
        </div>
        <div className='new-room'>
          <input 
            type="text"
            value={newRoomName}
            onChange={(e) => setNewRoomName(e.target.value)}
            placeholder="Nom de la nouvelle salle"
          />
          <button onClick={handleCreateRoom}>Créer</button>
        </div>
      </div>
      <div className='chat-log'>
        {messages.map((msg, index) => (
          <div 
            key={index} 
            className={`message ${msg.user === userName ? 'sent' : msg.type === 'system' ? 'system' : 'received'}`}>
              {msg.type === 'message' && <strong>{msg.user === userName ? 'Moi' : msg.user}: </strong>}
              {msg.text}
          </div>
        ))}
      </div>
      <div className='input-area'>
        <input 
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder="Ecrire un message..."
          onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
          />
          <button onClick={handleSendMessage}>Envoyer</button>
      </div>
    </div>
  )
}

export default App


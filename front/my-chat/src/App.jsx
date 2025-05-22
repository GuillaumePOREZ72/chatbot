import React, { useState, useEffect, useRef } from 'react'
import './App.css'

function App() {
  const [messages, setMessages] = useState([])
  const [inputValue, setInputValue] = useState('')
  const [userName, setUserName] = useState('') // pour le nom d'utilisateur
  const [isUserNameSet, setIsUserNameSet] = useState(false) // pour savoir si le nom d'utilisateur est défini
  const socketRef = useRef(null) // pour la référence du socket

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
    }

    socket.onmessage = (event) => {
      try {
        const receivedData = JSON.parse(event.data)
        console.log('Message du serveur:', receivedData);
        setMessages(prevMessages => [...prevMessages, receivedData]);
      } catch (error) {
        console.log('Message brut du serveur: ', event.data);
        setMessages(prevMessages => [ ...prevMessages, { type: 'message', user: 'Serveur', text: event.data }])
        
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
    if (inputValue.trim() && socketRef.current && socketRef.current.readyState === WebSocket.OPEN) {
      const messageData = {
        type: 'message', // Type de message
        user: userName, // Nom de l'utilisateur
        text: inputValue  // Contenu du message
      };
    socketRef.current.send(JSON.stringify(messageData));
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

  return (
    <div className='App'>
      <h1>Chat & WebSockets</h1>
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

import React, { useState, useRef, useEffect } from 'react';

// Main App component
function App() {
  // State to store the chat history
  const [chatHistory, setChatHistory] = useState([
    {
      role: 'model',
      parts: [{ text: 'Hello! Ask me to guess a movie based on its description.' }],
    },
  ]);
  // State for the user's current input
  const [userInput, setUserInput] = useState('');
  // State to indicate if the bot is currently processing a request
  const [isLoading, setIsLoading] = useState(false);
  // Ref for the chat display area to enable auto-scrolling
  const chatDisplayRef = useRef(null);

  // Scroll to the bottom of the chat display when chatHistory changes
  useEffect(() => {
    if (chatDisplayRef.current) {
      chatDisplayRef.current.scrollTop = chatDisplayRef.current.scrollHeight;
    }
  }, [chatHistory]);

  /**
   * Handles sending the user's message to the Django backend API.
   */
  const sendMessage = async () => {
    if (!userInput.trim()) return; // Don't send empty messages

    const newUserMessage = { role: 'user', parts: [{ text: userInput }] };
    // Optimistically update chat history with user's message
    setChatHistory((prev) => [...prev, newUserMessage]);
    setUserInput(''); // Clear input field
    setIsLoading(true); // Show loading indicator

    try {
      // --- IMPORTANT: Update this URL to your Django backend API endpoint ---
      // Ensure this matches the URL where your Django server is running
      // (e.g., if Django is on port 8000, and your API path is 'api/chat/')
      const djangoApiUrl = 'http://127.0.0.1:8000/api/chat/'; // Updated path

      const response = await fetch(djangoApiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message: newUserMessage.parts[0].text }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(`Backend API error: ${response.status} - ${errorData.error || response.statusText}`);
      }

      const result = await response.json();

      let modelResponseText = 'Sorry, I could not get a response from the chatbot.';
      if (result.response) {
        modelResponseText = result.response;
      }

      // Update chat history with model's response
      setChatHistory((prev) => [
        ...prev,
        { role: 'model', parts: [{ text: modelResponseText }] },
      ]);
    } catch (error) {
      console.error('Error sending message to backend:', error);
      setChatHistory((prev) => [
        ...prev,
        { role: 'model', parts: [{ text: `Error: ${error.message}. Please ensure your Django backend is running and accessible.` }] },
      ]);
    } finally {
      setIsLoading(false); // Hide loading indicator
    }
  };

  return (
    <div className="flex flex-col h-screen bg-gray-100 font-sans p-4 sm:p-6 md:p-8">
      <style>
        {`
          @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
          body { font-family: 'Inter', sans-serif; }
        `}
      </style>

      {/* Chat Display Area */}
      <div
        ref={chatDisplayRef}
        className="flex-1 overflow-y-auto p-4 bg-white rounded-lg shadow-md mb-4 border border-gray-200"
      >
        {chatHistory.map((message, index) => (
          <div
            key={index}
            className={`flex mb-4 ${
              message.role === 'user' ? 'justify-end' : 'justify-start'
            }`}
          >
            <div
              className={`max-w-[80%] p-3 rounded-lg shadow-sm ${
                message.role === 'user'
                  ? 'bg-blue-500 text-white rounded-br-none'
                  : 'bg-gray-200 text-gray-800 rounded-bl-none'
              }`}
            >
              <p className="whitespace-pre-wrap">{message.parts[0].text}</p>
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex justify-start mb-4">
            <div className="max-w-[80%] p-3 rounded-lg shadow-sm bg-gray-200 text-gray-800 rounded-bl-none animate-pulse">
              <p>Thinking...</p>
            </div>
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="flex items-center p-3 bg-white rounded-lg shadow-md border border-gray-200">
        <input
          type="text"
          className="flex-1 p-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 mr-3 text-gray-800"
          placeholder="Describe a movie..."
          value={userInput}
          onChange={(e) => setUserInput(e.target.value)}
          onKeyPress={(e) => {
            if (e.key === 'Enter' && !isLoading) {
              sendMessage();
            }
          }}
          disabled={isLoading}
        />
        <button
          onClick={sendMessage}
          className="px-6 py-3 bg-blue-600 text-white rounded-lg shadow-md hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 transition duration-200 ease-in-out disabled:opacity-50 disabled:cursor-not-allowed"
          disabled={isLoading}
        >
          Send
        </button>
      </div>
    </div>
  );
}

export default App;

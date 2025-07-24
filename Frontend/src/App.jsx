import { useState, useEffect } from "react";

function App() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState([]);
  const [sessionId, setSessionId] = useState("");
  const [showChat, setShowChat] = useState(false);
  const [movies, setMovies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [isTyping, setIsTyping] = useState(false);
  // Load movies and session ID on component mount
  useEffect(() => {
    // Load session ID
    const storedSessionId = localStorage.getItem("chat_session_id");
    if (storedSessionId) {
      setSessionId(storedSessionId);
    } else {
      const newSessionId = generateSessionId();
      localStorage.setItem("chat_session_id", newSessionId);
      setSessionId(newSessionId);
    }

    // Fetch movies
    const fetchMovies = async () => {
      try {
        const response = await fetch(
          "https://raw.githubusercontent.com/S1lver0/Json-Ia/refs/heads/master/cine_db.json"
        );
        const data = await response.json();
        setMovies(data.peliculas);
      } catch (error) {
        console.error("Error fetching movies:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchMovies();
  }, []);

  const generateSessionId = () => {
    return (
      Date.now().toString(36) + Math.random().toString(36).substring(2, 15)
    );
  };

  const enviarMensaje = async () => {
    if (!input.trim()) return;

    const nuevoMensaje = { role: "user", content: input };
    const nuevosMensajes = [...messages, nuevoMensaje];
    setMessages(nuevosMensajes);
    setInput("");
    setIsTyping(true);

    // Agregar mensaje vacío del bot para el efecto de escritura
    const botMessage = { role: "assistant", content: "" };
    setMessages([...nuevosMensajes, botMessage]);

    try {
      const respuesta = await fetch(
        `${import.meta.env.VITE_ENDPOINT_KEY}/chat`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            message: input,
            session_id: sessionId,
          }),
        }
      );

      const data = await respuesta.json();
      const respuestaBot = data.response;

      // Efecto de escritura
      let i = 0;
      const speed = 20; // Velocidad de escritura (ms por caracter)
      const typingInterval = setInterval(() => {
        if (i < respuestaBot.length) {
          const currentContent = respuestaBot.substring(0, i + 1);
          setMessages((prev) => {
            const newMessages = [...prev];
            newMessages[newMessages.length - 1].content = currentContent;
            return newMessages;
          });
          i++;
        } else {
          clearInterval(typingInterval);
          setIsTyping(false);
        }
      }, speed);
    } catch (err) {
      console.error("Error al conectar al chatbot:", err);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "No se pudo conectar con el servidor",
        },
      ]);
      setIsTyping(false);
    }
  };

  const toggleChat = () => {
    setShowChat(!showChat);
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-xl font-semibold">Cargando cartelera...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white">
      {/* Header */}
      <header className="bg-blue-900 py-4 px-6 shadow-lg">
        <div className="max-w-6xl mx-auto flex justify-between items-center">
          <h1 className="text-2xl font-bold">CineMax Premium</h1>
          <p className="text-blue-200">Centro Comercial Galerías</p>
        </div>
      </header>

      {/* Main Content - Movie Grid */}
      <main className="max-w-6xl mx-auto py-8 px-4">
        <h2 className="text-3xl font-bold mb-8 text-center">Cartelera</h2>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-8">
          {movies.map((movie) => (
            <div
              key={movie.id}
              className="bg-gray-800 rounded-lg overflow-hidden shadow-lg hover:shadow-xl transition-shadow"
            >
              <img
                src={movie.imagen}
                alt={movie.titulo}
                className="w-full h-64 object-cover"
              />
              <div className="p-4">
                <h3 className="text-xl font-bold mb-2">{movie.titulo}</h3>
                <div className="flex flex-wrap gap-2 mb-3">
                  {movie.genero.map((genre, i) => (
                    <span
                      key={i}
                      className="bg-blue-600 text-xs px-2 py-1 rounded"
                    >
                      {genre}
                    </span>
                  ))}
                </div>
                <p className="text-gray-300 text-sm mb-3 line-clamp-3">
                  {movie.sinopsis}
                </p>

                <div className="flex justify-between items-center mb-3">
                  <span className="bg-yellow-500 text-black px-2 py-1 rounded text-xs font-bold">
                    ★ {movie.rating}/10
                  </span>
                  <span className="text-sm">{movie.duracion} min</span>
                  <span className="text-sm">{movie.clasificacion}</span>
                </div>

                <div className="mt-4">
                  <h4 className="font-semibold mb-2">Horarios:</h4>
                  <div className="flex flex-wrap gap-2">
                    {movie.horarios.map((time, i) => (
                      <span
                        key={i}
                        className="bg-gray-700 px-2 py-1 rounded text-sm"
                      >
                        {time}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="mt-4">
                  <h4 className="font-semibold mb-2">Precios:</h4>
                  <div className="grid grid-cols-2 gap-2 text-sm">
                    <span>General: S/{movie.precios.general}</span>
                    <span>Niños: S/{movie.precios.niños}</span>
                    <span>Tercera edad: S/{movie.precios.tercera_edad}</span>
                    <span>VIP: S/{movie.precios.VIP}</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </main>

      {/* Chatbot Button */}
      <button
        onClick={toggleChat}
        className="fixed bottom-6 right-6 bg-blue-600 text-white p-4 rounded-full shadow-lg hover:bg-blue-700 transition-colors cursor-pointer"
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          className="h-8 w-8"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
          />
        </svg>
      </button>

      {/* Chatbot Container */}
      {showChat && (
        <div className="fixed bottom-24 right-6 w-96 h-[calc(100vh-10rem)] bg-white rounded-lg shadow-sm flex flex-col shadow-zinc-200">
          {/* Chat Header */}
          <div className="bg-blue-600 text-white p-4 rounded-t-lg flex justify-between items-center">
            <h3 className="font-bold">Asistente de CineMax</h3>
            <button
              onClick={toggleChat}
              className="text-white hover:text-gray-200"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                  clipRule="evenodd"
                />
              </svg>
            </button>
          </div>

          {/* Messages Area */}
          <div className="flex-1 p-4 overflow-y-auto h-64 bg-gray-50">
            {messages.length === 0 ? (
              <div className="text-center text-gray-500 py-4">
                Pregúntame sobre películas, horarios o promociones
              </div>
            ) : (
              messages.map((msg, idx) => (
                <div
                  key={idx}
                  className={`mb-3 ${
                    msg.role === "user" ? "text-right" : "text-left"
                  }`}
                >
                  <div
                    className={`inline-block px-4 py-2 rounded-lg max-w-xs ${
                      msg.role === "user"
                        ? "bg-blue-500 text-white"
                        : "bg-gray-200 text-gray-800"
                    }`}
                  >
                    {msg.content}
                    {/* Mostrar indicador de escritura solo para el último mensaje del bot */}
                    {isTyping &&
                      idx === messages.length - 1 &&
                      msg.role === "assistant" && (
                        <span className="ml-1 inline-block h-2 w-2 bg-gray-500 rounded-full animate-blink"></span>
                      )}
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Input Area */}
          <div className="p-4 border-t border-gray-300 bg-white">
            <div className="flex gap-2">
              <input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && enviarMensaje()}
                placeholder="Escribe tu mensaje..."
                className="flex-1 px-4 py-2 border border-gray-300 rounded focus:outline-none focus:ring-2 focus:ring-blue-500 text-black"
              />
              <button
                onClick={enviarMensaje}
                disabled={isTyping}
                className={`px-4 py-2 text-white rounded hover:bg-blue-700 cursor-pointer ${
                  isTyping ? "bg-blue-400" : "bg-blue-600"
                }`}
              >
                {isTyping ? "Escribiendo..." : "Enviar"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;

import json
import uuid
import os
import traceback
import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.ai.inference.models import SystemMessage, UserMessage
from azure.ai.inference import ChatCompletionsClient
from typing import List, Dict

load_dotenv()
endpoint = os.getenv("AZURE_INFERENCE_SDK_ENDPOINT")
model_name = os.getenv("DEPLOYMENT_NAME")
key = os.getenv("AZURE_INFERENCE_SDK_KEY")

if not all([endpoint, model_name, key]):
    raise ValueError(
        "Missing Azure environment variables: AZURE_INFERENCE_SDK_ENDPOINT, DEPLOYMENT_NAME, AZURE_INFERENCE_SDK_KEY")


try:
    client = ChatCompletionsClient(
        endpoint=endpoint, credential=AzureKeyCredential(key)
    )
except Exception as e:
    raise RuntimeError(f"Failed to initialize Azure client: {e}")


def load_movies() -> dict:
    """Loads movie data from the specified URL."""
    url = "https://raw.githubusercontent.com/S1lver0/Json-Ia/refs/heads/master/cine_db.json"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error loading movie data from URL: {e}")
        return {}
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {url}. Check the source.")
        return {}


def filter_by_category(category: str, value: str, data: dict):
    peliculas = data.get("peliculas", [])
    value = value.lower()
    if category == "genero":
        return [m for m in peliculas if value in [g.lower() for g in m.get("genero", [])]]
    elif category == "precio":
        try:
            max_price = float(value)
            return [m for m in peliculas if m.get("precios", {}).get("general", float('inf')) <= max_price]
        except (ValueError, TypeError):
            return []
    elif category == "promocion":
        return [m for m in peliculas if any(value in p.lower() for p in m.get("promociones", []))]
    elif category == "cartelera":
        return [m for m in peliculas if value in [h.lower() for h in m.get("horarios", [])]]
    return []


def format_movies(movies: List[Dict]) -> str:
    if not movies:
        return "No se encontraron películas que coincidan con tu búsqueda en nuestra base de datos."
    return "\n".join(
        f"- {m['titulo']} ({', '.join(m['genero'])}): {m['sinopsis'][:100]}..."
        for m in movies
    )


def format_promociones(promos: list) -> str:
    if not promos:
        return "No hay promociones generales disponibles."
    return "\n".join(f"• {p['nombre']}: {p['descripcion']}" for p in promos)


def format_combos(combos: list) -> str:
    if not combos:
        return "No hay combos disponibles."
    return "\n".join(f"• {c['nombre']}: {c['contenido']} (S/{c['precio']})" for c in combos)


def find_movie_by_title(title: str, data: dict) -> dict:
    """Busca una película por título (insensible a mayúsculas)"""
    peliculas = data.get("peliculas", [])
    title_lower = title.lower()
    for pelicula in peliculas:
        if title_lower in pelicula["titulo"].lower():
            return pelicula
    return None


def format_movie_details(movie: dict) -> str:
    """Formatea los detalles completos de una película"""
    if not movie:
        return "No encontré información sobre esa película."
    details = [
        f"🎬 **{movie['titulo']}**",
        f"📌 Género: {', '.join(movie['genero'])}",
        f"📝 Sinopsis: {movie['sinopsis']}",
        f"⏱️ Duración: {movie['duracion']} minutos",
        f"🎫 Clasificación: {movie['clasificacion']}",
        f"⏰ Horarios: {', '.join(movie['horarios'])}",
        "💲 Precios:",
        f"  - General: S/{movie['precios']['general']}",
        f"  - Niños: S/{movie['precios']['niños']}",
        f"  - Tercera edad: S/{movie['precios']['tercera_edad']}",
        f"  - VIP: S/{movie['precios']['VIP']}",
    ]
    if movie.get('promociones'):
        details.append(f"🎁 Promociones: {', '.join(movie['promociones'])}")
    details.append(f"⭐ Rating: {movie['rating']}/10")
    return "\n".join(details)


SYSTEM_PROMPT = '''Eres un asistente de cine para CineMax Premium. Debes seguir estas reglas estrictamente:
1. **SOLO** usa la información del contexto proporcionado. Nunca inventes datos.
2. Para detalles de películas, usa EXCLUSIVAMENTE la información del JSON.
3. Si no sabes algo, di amablemente que no tienes esa información.
4. Mantén respuestas breves y en español.
5. Para preguntas sobre películas específicas, muestra TODOS los detalles disponibles.'''


def detect_intent(question: str, generos_disponibles: list) -> tuple:
    """Detecta la intención del usuario con mejor precisión"""
    question_lower = question.lower()
    if any(word in question_lower for word in ["detalle", "información", "dime sobre", "hablame de", "qué sabes de"]):
        return "detalle_pelicula", {"titulo": question}
    for g in generos_disponibles:
        if g in question_lower:
            return "genero", {"genero": g}
    intent_map = [
        ("recomiend", "genero"), ("sugier", "genero"),
        ("cartelera", "cartelera"), ("horario", "cartelera"), ("hora",
                                                               "cartelera"), ("función", "cartelera"),
        ("precio", "precio"), ("coste", "precio"), ("valor",
                                                    "precio"), ("cuesta", "precio"),
        ("promocion", "promocion"), ("descuento",
                                     "promocion"), ("oferta", "promocion"),
        ("empresa", "empresa"), ("cine", "empresa"), ("ubicado",
                                                      "empresa"), ("dirección", "empresa")
    ]
    for keyword, intent in intent_map:
        if keyword in question_lower:
            return intent, {}
    return "empresa", {}


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://front-chat-bot.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

chat_histories: Dict[str, List[Dict[str, str]]] = {}


@app.post("/chat/history/clear")
async def clear_history(request: Request):
    """Limpia el historial de chat para una sesión específica"""
    try:
        body = await request.json()
        session_id = body.get("session_id")
        if not session_id:
            return JSONResponse(status_code=400, content={"error": "session_id is required"})
        if session_id in chat_histories:
            del chat_histories[session_id]
            return {"status": "success", "message": f"History for session {session_id} cleared."}
        else:
            return JSONResponse(status_code=404, content={"error": f"No history found for session {session_id}"})
    except Exception as e:
        print(traceback.format_exc())
        return JSONResponse(status_code=500, content={"error": f"An internal error occurred: {str(e)}"})


@app.post("/chat")
async def recibir_mensaje(request: Request):
    try:
        body = await request.json()
        question = body.get("message", "").lower()
        session_id = body.get("session_id")

        if not session_id:
            session_id = str(uuid.uuid4())
        if session_id not in chat_histories:
            chat_histories[session_id] = []

        history = chat_histories[session_id]
        history.append({"role": "user", "content": question})

        raw_data = load_movies()
        if not raw_data or "peliculas" not in raw_data:
            return JSONResponse(status_code=500, content={"response": "Lo siento, no pude cargar la información de las películas en este momento."})

        generos_disponibles = list(set(g.lower() for p in raw_data.get(
            "peliculas", []) for g in p.get("genero", [])))
        intent, entities = detect_intent(question, generos_disponibles)

        # Build the user prompt based on intent
        user_prompt = f"Historial de Conversación:\n"
        user_prompt += "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in history[-8:]])
        user_prompt += f"\n\nPregunta Actual: {question}\n\nContexto relevante:\n"

        if intent == "empresa":
            user_prompt += f"**Cine**: {raw_data.get('cine')}\n**Ubicación**: {raw_data.get('ubicacion')}\n**Promociones**: {format_promociones(raw_data.get('promociones_generales', []))}\n**Combos**: {format_combos(raw_data.get('combos', []))}"
        elif intent == "genero":
            genero = entities.get("genero", "acción")
            filtered = filter_by_category("genero", genero, raw_data)
            user_prompt += f"Películas de {genero}:\n{format_movies(filtered)}"
        elif intent == "cartelera":
            horario = entities.get("horario", "20:00")
            filtered = filter_by_category("cartelera", horario, raw_data)
            user_prompt += f"Películas para las {horario}:\n{format_movies(filtered)}"
        elif intent == "precio":
            precio = entities.get("precio", "35")
            filtered = filter_by_category("precio", precio, raw_data)
            user_prompt += f"Películas por menos de S/{precio}:\n{format_movies(filtered)}"
        elif intent == "promocion":
            promo = entities.get("promo", "2x1")
            filtered = filter_by_category("promocion", promo, raw_data)
            user_prompt += f"Películas con la promoción '{promo}':\n{format_movies(filtered)}"
        elif intent == "detalle_pelicula":
            movie = find_movie_by_title(entities.get("titulo", ""), raw_data)
            user_prompt += f"Detalles de la película:\n{format_movie_details(movie)}"
        else:
            user_prompt += "No se detectó una intención clara. Responde amablemente que no entiendes la pregunta."

        response = client.complete(
            messages=[
                SystemMessage(content=SYSTEM_PROMPT),
                UserMessage(content=user_prompt)
            ],
            model=model_name,
            max_tokens=1000,
            temperature=0.7
        )
        response_text = response.choices[0].message.content

        history.append({"role": "assistant", "content": response_text})
        chat_histories[session_id] = history

        return JSONResponse(content={"response": response_text, "session_id": session_id})

    except Exception as e:
        print(traceback.format_exc())
        return JSONResponse(status_code=500, content={"error": f"Ocurrió un error: {str(e)}"})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=int(
        os.environ.get("PORT", 8000)), reload=True)

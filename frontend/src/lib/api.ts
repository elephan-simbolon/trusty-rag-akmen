// VITE_API_BASE_URL diset di .env.local untuk development (http://localhost:8000).
// Pada production build (FastAPI melayani SPA dari origin yang sama),
// variabel ini sengaja tidak diset — fallback empty string membuat fetch
// menggunakan relative URL yang bekerja karena origin-nya sama.
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL || "";

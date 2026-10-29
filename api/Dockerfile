# Imagen de la API. Se construye desde la raíz del proyecto (context: . en el compose)
# porque necesita requirements.txt, que está afuera de api/.
FROM python:3.12-slim

WORKDIR /app

# Primero solo las dependencias: si el código cambia pero requirements.txt no, Docker
# reutiliza esta capa y el build no vuelve a instalar todo.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/ api/

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]


# Inicialización del Backend con FastAPI
Este proyecto utiliza FastAPI para crear un backend simple que responde a solicitudes HTTP. A continuación, se detallan los pasos para configurar y ejecutar el backend.
## Pasos para la Inicialización
1. Clona el repositorio y navega a la carpeta del proyecto:
   ```bash
    git clone https://github.com/JaimeGalindoV/youtube_back.git
    cd youtube_back
    ```
2. Instala las dependencias utilizando pip:
    ```bash
    pip install -r requirements.txt
    ```
3. Crea un archivo `.env` en la raíz del proyecto y agrega la URL de tu frontend (si es necesario):
    ```env
    FRONTEND_URL=http://localhost:5173
    ```
4. Inicia el servidor de desarrollo utilizando Uvicorn:
    ```bash
    uvicorn main:app --reload
    ```
5. Abre tu navegador y navega a `http://localhost:8000` para ver la respuesta del backend. Deberías ver un mensaje de bienvenida.
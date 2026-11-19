# PSN Live Code Detector v2 (Windows)

Detecta códigos de PlayStation Store dichos o mostrados en un YouTube LIVE. Se conecta a **una pestaña concreta de Chrome** (Playwright + Chrome DevTools Protocol), transcribe el audio de esa pestaña con faster-whisper y lee su imagen con OCR. Cuando aparece un candidato lo muestra en la tabla, lo deja seleccionado, emite un sonido y puede **preparar el canje**: abre la tienda de PlayStation y escribe el código en el campo, **sin pulsar nunca el botón final**.
<img width="902" height="882" alt="image" src="https://github.com/user-attachments/assets/5d076352-7b16-400c-98f5-6c9a28447892" />


## Novedades de la v2
- **Captura de una sola pestaña de Chrome** en lugar del monitor completo. La pestaña se elige en una lista; ya no importa en qué monitor esté ni qué haya delante.
- **Audio solo de esa pestaña**, leído directamente del vídeo. Opcionalmente se puede volver al audio del sistema.
- **Canje asistido con Playwright:** abre PlayStation Store, espera a que aparezca el campo del código y lo rellena. La persona revisa región/cuenta y confirma.
- **Modo de detección:** audio + OCR, solo audio o solo OCR.
- **Feed en pantalla** con todo lo transcrito y leído.
- **Selección automática** de cada código nuevo, listo para «Copiar seleccionado».

## Requisitos
- Windows 10/11 de 64 bits.
- Python 3.14 x64 (`install.bat` usa `py -3.14`).
- Google Chrome instalado.
- Conexión a Internet para descargar los modelos la primera vez (Whisper `small` y los modelos de OCR).
- GPU NVIDIA opcional. Whisper intenta CUDA y cae a CPU si falla. Las librerías CUDA 12 (cuBLAS y cuDNN) se instalan con `requirements.txt`; solo hace falta un driver NVIDIA reciente.

## Instalación
1. Ejecuta `install.bat` (crea `.venv` e instala `requirements.txt`).
2. Ejecuta `run.bat`.

## Uso
1. Pulsa **Abrir Chrome**. Se abre un Chrome con un perfil propio (`chrome-profile/`) y el puerto de depuración activado. Chrome 136 o superior ignora ese puerto con tu perfil normal, por eso hace falta un perfil aparte. **La primera vez**, inicia sesión en YouTube y en PlayStation en esa ventana; la sesión queda guardada.
2. Abre el YouTube LIVE en esa ventana de Chrome.
3. Pulsa **Actualizar** y elige la pestaña. Si hay una de YouTube, se preselecciona.
4. Elige **Detectar con**: *Audio + OCR*, *Solo audio* o *Solo OCR*. El intervalo de OCR (1 a 10 s) controla cada cuánto se captura la pestaña.
5. Pulsa **Iniciar monitoreo**. Lo que se transcribe y se lee aparece en el feed.
6. Cuando se detecta un código queda seleccionado en la tabla:
   - **Copiar seleccionado:** lo copia al portapapeles (el aviso aparece en la barra de estado).
   - **Limpiar códigos** / **Limpiar feed:** vacían la tabla o el feed. Un código ya detectado no vuelve a aparecer aunque siga en pantalla, hasta que pulses **Detener** e **Iniciar monitoreo** de nuevo.
   - **Abrir canje oficial:** lo copia, abre `store.playstation.com/redeem` en el Chrome del monitoreo, espera hasta 5 minutos a que aparezca el campo (inicia sesión si hace falta) y escribe el código. Revisa región y cuenta, y pulsa tú mismo el botón de canje.

### Audio
La casilla **Audio solo de la pestaña** está activada por defecto: la app lee el `<video>` de la pestaña y no depende del dispositivo de salida de Windows. Si no transcribe nada, desmárcala para usar el audio del sistema por loopback del dispositivo de salida predeterminado de Windows (en ese caso se oye todo lo que suene en el equipo).

## Limitaciones
- **La ventana de Chrome no debe estar minimizada** y la pestaña debe ser la activa de su ventana: Chrome puede no devolver la imagen de una pestaña oculta. Si la captura falla, la barra de estado lo avisa. No se ha comprobado qué pasa cuando otras ventanas tapan la de Chrome.
- La extracción de códigos es heurística: un patrón válido (3 grupos de 4 caracteres con al menos un dígito) no significa que el código exista, esté activo o pertenezca a tu región. Puede haber falsos positivos.
- El campo del código en la página de PlayStation se localiza por heurística (placeholder, `aria-label`, nombre o id con «code»/«código»). Si PlayStation cambia la página, puede no encontrarlo y habrá que pegar el código a mano; ya está en el portapapeles.
- **Nunca se pulsa el botón de canje ni se valida el código con PlayStation.** El canje siempre lo confirma una persona.
- La captura de audio de la pestaña y el canje se han probado con páginas locales; el comportamiento con un LIVE real o con cambios en la web de PlayStation puede variar.

## Privacidad y seguridad
- El procesamiento es local: el audio y las capturas no se suben a ningún servidor de esta aplicación. Solo la descarga inicial de modelos usa Internet.
- La app no solicita ni guarda credenciales de PlayStation. Pero **`chrome-profile/` contiene las sesiones (cookies) de las cuentas en las que inicies sesión**: no la compartas ni la incluyas en un ZIP.
- Mientras el Chrome de monitoreo está abierto, el puerto de depuración `127.0.0.1:9222` permite controlarlo a cualquier programa de tu equipo. Solo escucha en local; ciérralo cuando no lo uses.

## Solución de problemas
- **«Chrome no está abierto con CDP»:** pulsa **Abrir Chrome**. Si ya tenías Chrome abierto con otro perfil, no sirve: se usa el perfil `chrome-profile/`.
- **No aparece mi pestaña:** pulsa **Actualizar**; solo se listan pestañas del Chrome lanzado por la app.
- **No transcribe:** comprueba que el vídeo se está reproduciendo con sonido. Si sigue sin transcribir, desmarca *Audio solo de la pestaña*.
- **No lee texto / error de captura:** la ventana no debe estar minimizada. Agranda el reproductor y evita que el código quede tapado.
- **`cublas64_12.dll` no encontrada:** reinstala dependencias con `pip install -r requirements.txt` (incluye `nvidia-cublas-cu12` y `nvidia-cudnn-cu12`). Si CUDA no funciona, se usa CPU automáticamente.
- **No encuentra el campo de canje:** inicia sesión en la ventana que se abrió, espera unos segundos y, si no se rellena, pega el código (ya está en el portapapeles).

const cameraOption = document.getElementById('cameraOption');
const fileOption = document.getElementById('fileOption');
const cameraInput = document.getElementById('cameraInput');
const fileInput = document.getElementById('fileInput');
const selectedFile = document.getElementById('selectedFile');
const fileName = document.getElementById('fileName');
const fileSize = document.getElementById('fileSize');
const clearBtn = document.getElementById('clearBtn');
const responseMessage = document.getElementById('responseMessage');
const responseTitle = document.getElementById('responseTitle');
const responseText = document.getElementById('responseText');
const responseMetadata = document.getElementById('responseMetadata');

// Camera modal elements
const cameraModal = document.getElementById('cameraModal');
const cameraFeed = document.getElementById('cameraFeed');
const cameraCanvas = document.getElementById('cameraCanvas');
const captureBtn = document.getElementById('captureBtn');
const closeCameraBtn = document.getElementById('closeCameraBtn');
const switchCameraBtn = document.getElementById('switchCameraBtn');
const cameraFrame = document.querySelector('.camera-frame');

const CAMERA_CAPTURE_SCALE = 2;

let selectedFileData = null;
let cameraStream = null;
let isCameraActive = false;
let videoDevices = [];
let currentDeviceIndex = 0;

// Camera option handlers - open camera via MediaDevices API
cameraOption.addEventListener('click', async () => {
    try {
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            await openCameraModal();
        } else {
            cameraInput.click();
        }
    } catch (error) {
        console.log('Camera not available, using file input fallback');
        cameraInput.click();
    }
});

cameraInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        void handleFileSelect(e.target.files[0]);
    }
});

// File option handlers
fileOption.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        void handleFileSelect(e.target.files[0]);
    }
});

// Camera Modal Functions
async function openCameraModal() {
    try {
        cameraModal.style.display = 'flex';
        await loadVideoDevices();
        await startCameraStream();
    } catch (error) {
        console.error('Error accessing camera:', error);
        showError('No se pudo acceder a la cámara. Por favor, verifica los permisos.');
        closeCameraModal();
    }
}

async function loadVideoDevices() {
    if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
        videoDevices = [];
        return;
    }

    const devices = await navigator.mediaDevices.enumerateDevices();
    videoDevices = devices.filter(device => device.kind === 'videoinput');
    if (currentDeviceIndex >= videoDevices.length) {
        currentDeviceIndex = 0;
    }
}

async function startCameraStream() {
    if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
    }

    const deviceId = videoDevices[currentDeviceIndex]?.deviceId;
    const constraints = {
        video: deviceId
            ? { deviceId: { exact: deviceId }, width: { ideal: 1920 }, height: { ideal: 1080 } }
            : { facingMode: 'environment', width: { ideal: 1920 }, height: { ideal: 1080 } },
        audio: false
    };

    cameraStream = await navigator.mediaDevices.getUserMedia(constraints);
    cameraFeed.srcObject = cameraStream;
    isCameraActive = true;

    if (videoDevices.length <= 1) {
        switchCameraBtn.disabled = true;
        switchCameraBtn.style.opacity = '0.5';
    } else {
        switchCameraBtn.disabled = false;
        switchCameraBtn.style.opacity = '1';
    }
}

function closeCameraModal() {
    if (cameraStream) {
        cameraStream.getTracks().forEach(track => track.stop());
        cameraStream = null;
    }
    cameraModal.style.display = 'none';
    isCameraActive = false;
}

closeCameraBtn.addEventListener('click', closeCameraModal);

function getFrameCropRect() {
    if (!cameraFrame) return null;

    const videoRect = cameraFeed.getBoundingClientRect();
    const frameRect = cameraFrame.getBoundingClientRect();

    const displayWidth = videoRect.width;
    const displayHeight = videoRect.height;
    const videoWidth = cameraFeed.videoWidth;
    const videoHeight = cameraFeed.videoHeight;

    if (!videoWidth || !videoHeight || !displayWidth || !displayHeight) {
        return null;
    }

    // Map frame from CSS pixels to video pixels (object-fit: cover)
    const scale = Math.max(displayWidth / videoWidth, displayHeight / videoHeight);
    const scaledWidth = videoWidth * scale;
    const scaledHeight = videoHeight * scale;
    const offsetX = (displayWidth - scaledWidth) / 2;
    const offsetY = (displayHeight - scaledHeight) / 2;

    const frameX = frameRect.left - videoRect.left;
    const frameY = frameRect.top - videoRect.top;
    const frameW = frameRect.width;
    const frameH = frameRect.height;

    let srcX = (frameX - offsetX) / scale;
    let srcY = (frameY - offsetY) / scale;
    let srcW = frameW / scale;
    let srcH = frameH / scale;

    if (srcX < 0) {
        srcW += srcX;
        srcX = 0;
    }
    if (srcY < 0) {
        srcH += srcY;
        srcY = 0;
    }
    if (srcX + srcW > videoWidth) {
        srcW = videoWidth - srcX;
    }
    if (srcY + srcH > videoHeight) {
        srcH = videoHeight - srcY;
    }

    return { x: srcX, y: srcY, width: srcW, height: srcH };
}

captureBtn.addEventListener('click', () => {
    if (!isCameraActive) return;

    const context = cameraCanvas.getContext('2d');
    const crop = getFrameCropRect();
    if (crop && crop.width > 0 && crop.height > 0) {
        cameraCanvas.width = Math.round(crop.width * CAMERA_CAPTURE_SCALE);
        cameraCanvas.height = Math.round(crop.height * CAMERA_CAPTURE_SCALE);
        context.drawImage(
            cameraFeed,
            crop.x,
            crop.y,
            crop.width,
            crop.height,
            0,
            0,
            cameraCanvas.width,
            cameraCanvas.height
        );
    } else {
        cameraCanvas.width = Math.round(cameraFeed.videoWidth * CAMERA_CAPTURE_SCALE);
        cameraCanvas.height = Math.round(cameraFeed.videoHeight * CAMERA_CAPTURE_SCALE);
        context.drawImage(cameraFeed, 0, 0, cameraCanvas.width, cameraCanvas.height);
    }

    cameraCanvas.toBlob((blob) => {
        const file = new File([blob], `camera-${Date.now()}.jpg`, { type: 'image/jpeg' });
        void handleFileSelect(file);
        closeCameraModal();
    }, 'image/jpeg', 0.95);
});

switchCameraBtn.addEventListener('click', async () => {
    if (videoDevices.length <= 1) {
        return;
    }

    currentDeviceIndex = (currentDeviceIndex + 1) % videoDevices.length;
    try {
        await startCameraStream();
    } catch (error) {
        console.error('Error switching camera:', error);
        showError('No se pudo cambiar la cámara.');
    }
});

async function handleFileSelect(file, { compress = true, maxBytes = 1024 * 1024 } = {}) {
    // Limpiar resultado previo al seleccionar/capturar una foto
    responseMessage.classList.remove('show');
    responseTitle.textContent = '';
    responseText.textContent = '';
    responseMetadata.innerHTML = '';
    if (!file.type.startsWith('image/')) {
        showError('Por favor selecciona una imagen');
        return;
    }

    let normalizedFile = file;
    if (compress) {
        try {
            normalizedFile = await compressImageFile(file, { maxBytes });
        } catch (error) {
            console.error('Error compressing image:', error);
        }
    }

    if (normalizedFile.size > maxBytes) {
        const maxSizeInMB = Math.round((maxBytes / (1024 * 1024)) * 100) / 100;
        showError(`La imagen no puede ser mayor a ${maxSizeInMB} MB. Tu archivo es de ${formatFileSize(normalizedFile.size)}`);
        return;
    }

    selectedFileData = normalizedFile;
    fileName.textContent = `Archivo: ${normalizedFile.name}`;
    fileSize.textContent = `Tamaño: ${formatFileSize(normalizedFile.size)}`;
    selectedFile.classList.add('show');

    // Mostrar vista previa y overlay de análisis
    const previewContainer = document.getElementById('previewContainer');
    const previewImage = document.getElementById('previewImage');
    const analyzingOverlay = document.getElementById('analyzingOverlay');
    if (previewContainer && previewImage && analyzingOverlay) {
        previewContainer.style.display = 'block';
        previewImage.src = URL.createObjectURL(normalizedFile);
        analyzingOverlay.style.display = 'flex';
    }

    // Iniciar análisis automáticamente
    await uploadPhoto();
    // Ocultar overlay de análisis al terminar
    if (analyzingOverlay) {
        analyzingOverlay.style.display = 'none';
    }
}

function compressImageFile(file, { maxBytes } = {}) {
    const maxDimension = 1280;
    const minDimension = 640;
    const minQuality = 0.6;
    const qualityStep = 0.08;
    const scaleStep = 0.85;
    const maxTargetBytes = maxBytes || 1024 * 1024;

    return new Promise((resolve, reject) => {
        const img = new Image();
        const objectUrl = URL.createObjectURL(file);

        img.onload = async () => {
            let { width, height } = img;
            const initialScale = Math.min(1, maxDimension / Math.max(width, height));
            width = Math.max(1, Math.round(width * initialScale));
            height = Math.max(1, Math.round(height * initialScale));

            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            let quality = 0.9;
            let blob = null;

            while (true) {
                canvas.width = width;
                canvas.height = height;
                ctx.drawImage(img, 0, 0, width, height);

                blob = await new Promise((resolveBlob) => {
                    canvas.toBlob(
                        resolveBlob,
                        'image/jpeg',
                        quality
                    );
                });

                if (!blob) {
                    URL.revokeObjectURL(objectUrl);
                    reject(new Error('No se pudo comprimir la imagen'));
                    return;
                }

                if (blob.size <= maxTargetBytes) {
                    break;
                }

                if (quality - qualityStep >= minQuality) {
                    quality -= qualityStep;
                    continue;
                }

                if (Math.max(width, height) <= minDimension) {
                    break;
                }

                width = Math.max(1, Math.round(width * scaleStep));
                height = Math.max(1, Math.round(height * scaleStep));
                quality = 0.9;
            }

            URL.revokeObjectURL(objectUrl);
            const compressedName = file.name.replace(/\.(png|webp|bmp|gif|jpeg|jpg)$/i, '.jpg');
            resolve(new File([blob], compressedName, { type: 'image/jpeg' }));
        };

        img.onerror = () => {
            URL.revokeObjectURL(objectUrl);
            reject(new Error('No se pudo leer la imagen'));
        };

        img.src = objectUrl;
    });
}


async function uploadPhoto() {
    if (!selectedFileData) {
        showError('Selecciona una foto primero');
        return;
    }

    const formData = new FormData();
    formData.append('file', selectedFileData);

    try {
        const response = await fetch('/api/upload-photo', {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (data.status === 'success') {
            showSuccess(data);
            cameraInput.value = '';
            fileInput.value = '';
            selectedFileData = null;
            selectedFile.classList.remove('show');
        } else {
            showError(data.message || 'Error al subir la foto');
        }
    } catch (error) {
        showError(`Error: ${error.message}`);
    }
}

function showSuccess(data) {
    const validation = data.validation;
    const isValid = validation.valid === true;
    const validationDetails = validation.validation_details || {};
    const serials = data.serials || [];
    
    // Caso 1: Si valid = true, serials está vacío y validation_details está vacío → error "Billete no encontrado"
    if (isValid && serials.length === 0 && Object.keys(validationDetails).length === 0) {
        responseMessage.classList.add('show', 'error');
        responseMessage.classList.remove('success');
        responseTitle.textContent = '❌ No se pudo identificar un billete en la imagen. Verifique que el billete esté visible y enfocado.';
        responseText.textContent = '';
        responseMetadata.innerHTML = '';
        return;
    }
    
    // Caso 2: Si valid = true y serials no está vacío → success
    if (isValid && serials.length > 0) {
        responseMessage.classList.add('show', 'success');
        responseMessage.classList.remove('error');
        responseTitle.textContent = '✅ ' + validation.message;
        responseText.textContent = '';
        
        let metadataHTML = `
            <div class="metadata-item valid">
                <span class="metadata-label">Estado:</span>
                <span class="metadata-value">✓ Verificado</span>
            </div>
        `;
        
        // Agregar imagen anotada si existe
        if (data.annotated_image_base64) {
            metadataHTML += `
                <div class="annotated-image-container">
                    <img src="data:image/jpeg;base64,${data.annotated_image_base64}" class="annotated-image" alt="Imagen anotada del billete">
                </div>
            `;
        }
        
        responseMetadata.innerHTML = metadataHTML;
        return;
    }
    
    // Caso 3: Si valid = false → mostrar error con detalles del validation_details
    if (!isValid) {
        responseMessage.classList.add('show', 'error');
        responseMessage.classList.remove('success');
        responseTitle.textContent = '❌ ' + validation.message;
        responseText.textContent = '';
        
        let metadataHTML = ``;
        
        // Agregar serial si existe
        if (validationDetails.serial) {
            metadataHTML += `
                <div class="metadata-item invalid">
                    <span class="metadata-label">Serie:</span>
                    <span class="metadata-value">${validationDetails.serial}</span>
                </div>
            `;
        }
        
        // Agregar rango si existe
        if (validationDetails.range) {
            metadataHTML += `
                <div class="metadata-item invalid">
                    <span class="metadata-label">Rango:</span>
                    <span class="metadata-value">${validationDetails.range}</span>
                </div>
            `;
        }
        
        // Agregar denominación si existe
        if (validationDetails.denom) {
            metadataHTML += `
                <div class="metadata-item invalid">
                    <span class="metadata-label">Denominación:</span>
                    <span class="metadata-value">Bs. ${validationDetails.denom}</span>
                </div>
            `;
        }
        
        // Agregar imagen anotada si existe
        if (data.annotated_image_base64) {
            metadataHTML += `
                <div class="annotated-image-container">
                    <img src="data:image/jpeg;base64,${data.annotated_image_base64}" class="annotated-image" alt="Imagen anotada del billete">
                </div>
            `;
        }
        
        responseMetadata.innerHTML = metadataHTML;
    }
}

function showError(message) {
    responseMessage.classList.add('show', 'error');
    responseMessage.classList.remove('success');
    responseTitle.textContent = '❌ Error';
    responseText.textContent = message;
    responseMetadata.innerHTML = '';
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

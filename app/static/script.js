const cameraOption = document.getElementById('cameraOption');
const fileOption = document.getElementById('fileOption');
const cameraInput = document.getElementById('cameraInput');
const fileInput = document.getElementById('fileInput');
const selectedFile = document.getElementById('selectedFile');
const fileName = document.getElementById('fileName');
const fileSize = document.getElementById('fileSize');
const uploadBtn = document.getElementById('uploadBtn');
const clearBtn = document.getElementById('clearBtn');
const loading = document.getElementById('loading');
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

let selectedFileData = null;
let cameraStream = null;
let isCameraActive = false;
let videoDevices = [];
let currentDeviceIndex = 0;

// Camera option handlers - open camera via MediaDevices API
cameraOption.addEventListener('click', async () => {
    try {
        // First try MediaDevices API (modern approach)
        if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
            await openCameraModal();
        } else {
            // Fallback to file input
            cameraInput.click();
        }
    } catch (error) {
        console.log('Camera not available, using file input fallback');
        cameraInput.click();
    }
});

cameraInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFileSelect(e.target.files[0]);
    }
});

// File option handlers
fileOption.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length > 0) {
        handleFileSelect(e.target.files[0]);
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
            ? { deviceId: { exact: deviceId }, width: { ideal: 1280 }, height: { ideal: 720 } }
            : { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
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

captureBtn.addEventListener('click', () => {
    if (!isCameraActive) return;

    const context = cameraCanvas.getContext('2d');
    cameraCanvas.width = cameraFeed.videoWidth;
    cameraCanvas.height = cameraFeed.videoHeight;
    context.drawImage(cameraFeed, 0, 0);

    cameraCanvas.toBlob((blob) => {
        const file = new File([blob], `camera-${Date.now()}.jpg`, { type: 'image/jpeg' });
        handleFileSelect(file);
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

function handleFileSelect(file) {
    if (!file.type.startsWith('image/')) {
        showError('Por favor selecciona una imagen');
        return;
    }

    const maxSizeInMB = 5;
    const maxSizeInBytes = maxSizeInMB * 1024 * 1024;
    if (file.size > maxSizeInBytes) {
        showError(`La imagen no puede ser mayor a ${maxSizeInMB} MB. Tu archivo es de ${formatFileSize(file.size)}`);
        return;
    }

    selectedFileData = file;
    fileName.textContent = `Archivo: ${file.name}`;
    fileSize.textContent = `Tamaño: ${formatFileSize(file.size)}`;
    selectedFile.classList.add('show');
    uploadBtn.disabled = false;
}

clearBtn.addEventListener('click', () => {
    cameraInput.value = '';
    fileInput.value = '';
    selectedFileData = null;
    selectedFile.classList.remove('show');
    uploadBtn.disabled = true;
    responseMessage.classList.remove('show');
});

uploadBtn.addEventListener('click', uploadPhoto);

async function uploadPhoto() {
    if (!selectedFileData) {
        showError('Selecciona una foto primero');
        return;
    }

    const formData = new FormData();
    formData.append('file', selectedFileData);

    loading.style.display = 'block';
    uploadBtn.disabled = true;

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
    } finally {
        loading.style.display = 'none';
        uploadBtn.disabled = !selectedFileData;
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
        responseTitle.textContent = '❌ Billete no encontrado';
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

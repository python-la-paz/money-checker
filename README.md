# 🇧🇴 Billete Verificador

Aplicación web de código abierto para la **verificación referencial de series de billetes** observados por el Banco Central de Bolivia (BCB), desarrollada por la comunidad **Python La Paz**.

🌐 **Versión en línea:** [bob.pylapaz.org](https://bob.pylapaz.org)

> ⚠️ **Aviso importante**
> Esta herramienta es de apoyo informativo. No es un servicio oficial del BCB ni reemplaza los canales formales de verificación.

---

## Contexto

Tras el accidente aéreo ocurrido el 17 de febrero de 2026 en la ciudad de El Alto, el Banco Central de Bolivia emitió comunicados inhabilitando ciertas series de billetes. Esta aplicación permite a los ciudadanos verificar de forma rápida y sencilla si un billete pertenece a una serie observada, utilizando la cámara del dispositivo o una imagen existente.

La información de series inhabilitadas se actualiza conforme a los comunicados oficiales del BCB. Consulte el [comunicado vigente](https://www.bcb.gob.bo/webdocs/files_noticias/28feb26%20CP%209%20BCB%20levanta%20inhabilitaci%C3%B3n%20Serie%20B.PDF).

---

## Características

- 📷 **Captura con cámara** — Fotografía el billete directamente desde el navegador
- 🖼️ **Carga desde galería** — Sube imágenes existentes para su análisis
- 🔍 **OCR de serie** — Lectura asistida del número de serie mediante reconocimiento óptico
- ✅ **Validación referencial** — Comparación contra los listados publicados por el BCB

---

## Stack Tecnológico

| Componente | Tecnología |
|---|---|
| Backend | FastAPI (Python 3.11) |
| Frontend | HTML5, CSS3, JavaScript (vanilla) |
| OCR | EasyOCR + OpenCV |
| Base de datos | MongoDB 7.0 (Motor async) |
| Contenedorización | Docker + Docker Compose |
| GeoIP | MaxMind GeoIP2 |

---

## Levantar en Local

### Prerrequisitos

- [Docker](https://docs.docker.com/get-docker/) y [Docker Compose](https://docs.docker.com/compose/install/) instalados
- Git

### 1. Clonar el repositorio

```bash
git clone https://github.com/python-la-paz/money-checker.git
cd money-checker
```

### 2. Configurar variables de entorno

Crea un archivo `.env` en la raíz del proyecto con las variables necesarias. Puedes usar el siguiente ejemplo como base:

```env
MONGODB_URL=mongodb://admin:change_me_deploy@mongodb:27017/?authSource=admin
DATABASE_NAME=money_checker
UPLOAD_DIR=/app/uploads
```

### 3. Levantar con Docker Compose (desarrollo)

```bash
docker compose -f compose.dev.yml up -d --build
```

Esto levanta dos servicios:
- **MongoDB** en el puerto `27017`
- **App** en el puerto `8000`

### 4. Acceder a la aplicación

Abre tu navegador en [http://localhost:8000](http://localhost:8000)

### Detener los servicios

```bash
docker compose -f compose.dev.yml down
```

---

## Acerca de Python La Paz

[Python La Paz](https://pylapaz.org/) es una comunidad abierta de desarrolladores que promueve el aprendizaje, la colaboración y la creación de herramientas tecnológicas con impacto local en Bolivia.

- 🌐 [pylapaz.org](https://pylapaz.org/)
- 📧 [hello@pylapaz.org](mailto:hello@pylapaz.org)
- 🐙 [github.com/python-la-paz](https://github.com/python-la-paz)

---

## Contribuciones

Las contribuciones son bienvenidas. Puedes revisar el código, abrir issues o enviar pull requests.

<a href="https://github.com/python-la-paz/money-checker/graphs/contributors">
    <img src="https://contrib.rocks/image?repo=python-la-paz/money-checker" />
</a>

---

## Licencia

Este proyecto está licenciado bajo la [GNU General Public License v3.0](LICENSE).

---

Con mucho ❤️ **Python La Paz** 🐍 [![Web](https://img.shields.io/badge/Web-Python%20La%20Paz-blue.svg)](https://pylapaz.org/)

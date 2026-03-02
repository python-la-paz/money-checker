# 🇧🇴 Verificador Serie – *_Python La Paz_* 💻🚀

Repositorio del proyecto **Verificador Serie**, una aplicación web de código abierto para la **identificación referencial de billetes Serie "B" observados por el Banco Central de Bolivia (BCB)** tras el siniestro.

Proyecto impulsado por la comunidad, desarrollado por la comunidad, para la comunidad.

> ⚠️ **Nota importante**  
> Esta herramienta es de apoyo informativo. No es un servicio oficial del BCB ni reemplaza los canales formales de verificación.

---

## Enlace principal 🌐

- [https://bob.pylapaz.org](https://bob.pylapaz.org)

---

## Características 📌

- **Captura con cámara**: Toma fotos del billete desde el navegador.
- **Carga desde galería**: Sube imágenes existentes.
- **OCR de serie**: Lectura asistida del número de serie
- **Validación referencial**: Comparación contra listados publicados por el BCB.

---

## Stack Tecnológico 🧱

- **Backend**: FastAPI (Python)
- **Frontend**: HTML5, CSS3, JavaScript (vanilla)

## Despliegue en pruebas 🚀

Utiliza Docker Compose para levantar la aplicación localmente:

```bash
docker-compose -f compose.dev.yaml build
docker-compose -f compose.dev.yaml up -d
```
O también de forma más compacta:

```bash
docker compose -f compose.dev.yaml up -d --build
```

---

## Contribuciones 🤝

<a href="https://github.com/python-la-paz/money-checker/graphs/contributors">
    <img src="https://contrib.rocks/image?repo=python-la-paz/money-checker" />
</a>

### Con mucho ❤️ Python La Paz 🐍 [![Pagina Web](https://img.shields.io/badge/Web-Python%20La%20Paz-blue.svg)](https://pylapaz.org/)

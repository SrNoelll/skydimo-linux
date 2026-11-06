<div align="center">

<img src="../ambiluz/icon.svg" width="110" alt="Logo de Ambiluz">

# Ambiluz — Skydimo para Linux

**La app para Linux que le faltaba a las luces de monitor Skydimo.**
Sincronización con la pantalla tipo Ambilight en Wayland y X11, modo música, efectos e icono en la bandeja. Sin necesitar la app de Windows.

[English](../README.md) · **Español** · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Русский](README.ru.md) · [Français](README.fr.md)

<img src="img/demo.gif" width="640" alt="Vista previa en vivo de Ambiluz">

</div>

## ⚡ Instalación (una línea)

```bash
curl -fsSL https://raw.githubusercontent.com/SrNoelll/skydimo-linux/main/install.sh | bash
```

Funciona en **Arch / CachyOS / Manjaro / EndeavourOS, Debian / Ubuntu / Mint / Pop!_OS, Fedora / Nobara y openSUSE**.
El instalador pone las dependencias (pregunta antes), añade la app al menú, el comando `ambiluz` y una regla udev para
que la tira funcione sin tocar grupos. Conecta la tira y abre **Ambiluz** desde el menú de aplicaciones.

Desinstalar:

```bash
curl -fsSL https://raw.githubusercontent.com/SrNoelll/skydimo-linux/main/install.sh | bash -s -- --uninstall
```

Arch (PKGBUILD listo para AUR): `git clone https://github.com/SrNoelll/skydimo-linux.git && cd skydimo-linux/packaging/aur && makepkg -si`

## ✨ Funciones

- 🖥 **Sincronizar pantalla (Ambilight):** pantalla completa, mitad superior / inferior / izquierda / derecha y **modo película**.
  **Detección automática de bandas negras**, suavizado, saturación, gamma y profundidad. Captura mediante
  **xdg-desktop-portal + PipeWire** (KDE Plasma, GNOME, Hyprland, Sway…) o directamente en **X11**. Recuerda la pantalla
  elegida para no preguntar cada vez.
- 🎵 **Música:** reacciona a lo que suena en el PC (o al micrófono): **Espectro, Pulso, Vúmetro, Ondas, Arcoíris rítmico y Graves**.
- 🌈 **Flujo:** Arcoíris, Degradado, Aurora, Ola, Respiración, Ciclo de color, Destellos y Fuego, con 13 paletas.
- 🎨 **Monocromo:** selector de color con efectos Fijo, Respiración, Latido, Vela y Parpadeo.
- 🏇 **Carrera de luces (跑马灯):** Carrera de caballos, Marquesina, Cometa, Escáner y Bloques.
- 🔌 **Conectar y listo:** detecta el puerto y el **modelo**, se reconecta si desenchufas la tira y aguanta la suspensión.
- 🛠 **Calibración:** identificar lados, recorrido LED a LED, pruebas RGB, dirección, desplazamiento, orden de color y balance de blancos.
- 🧰 **Integración:** bandeja del sistema, inicio con la sesión, apagado al bloquear o suspender, fundidos suaves y línea de comandos.
- 🌍 **6 idiomas:** español, inglés, chino, japonés, ruso y francés.

## 🔦 Modelos compatibles

Tiras y barras Skydimo con el controlador USB **CH340** (`1a86:7523`): SK0121, SK0124, **SK0127**, SK0132, SK0134,
SK0149, SKA124/127/132/134, SK0L21/24/27/32/34, SK0201/0202/0204, SK0F01/F02, SK0402/0403. ¿Tu modelo no aparece?
Usa un diseño personalizado y [abre un issue](https://github.com/SrNoelll/skydimo-linux/issues/new?template=new_model.yml).

## ⌨️ Línea de comandos

```bash
ambiluz --toggle           # encender/apagar (asígnalo a un atajo de teclado)
ambiluz --mode music       # sync | flow | mono | music | race
ambiluz --brightness 60
ambiluz --color ff6a00
ambiluz --probe            # detecta la tira y muestra modelo y LEDs
```

## ❓ Problemas frecuentes

- **No encuentra la tira:** ejecuta `ambiluz --probe`, acepta la regla udev del instalador y vuelve a enchufar la tira.
  En Ubuntu/Debian desinstala `brltty` (se apropia de los CH340). Cierra OpenRGB, HyperHDR o Prismatik si están abiertos.
- **La sincronización no arranca:** en Wayland el sistema pregunta qué pantalla compartir; elige la de las luces.
  Instala el backend del portal de tu escritorio (`xdg-desktop-portal-kde`, `-gnome`, `-hyprland` o `-wlr`).
- **Izquierda y derecha al revés:** Ajustes → Calibración → *Identificar lados* y cambia la **Dirección**.

Proyecto independiente y no oficial, sin relación con Skydimo. Licencia [GPL-3.0](../LICENSE).
Si te resulta útil, **una ⭐ ayuda a que otros usuarios de Linux lo encuentren.**

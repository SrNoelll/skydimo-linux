<div align="center">

<img src="../ambiluz/icon.svg" width="110" alt="Ambiluz">

# Ambiluz — Skydimo pour Linux

**L'application Linux qui manquait aux éclairages d'écran Skydimo.**
Synchro écran façon Ambilight sur Wayland et X11, mode musique, effets et icône dans la barre d'état. Pas besoin de l'application Windows.

[English](../README.md) · [Español](README.es.md) · [简体中文](README.zh-CN.md) · [日本語](README.ja.md) · [Русский](README.ru.md) · **Français**

<img src="img/demo.gif" width="640" alt="Aperçu en direct d'Ambiluz">

</div>

## ⚡ Installation en une ligne

```bash
curl -fsSL https://raw.githubusercontent.com/SrNoelll/skydimo-linux/main/install.sh | bash
```

Fonctionne sous **Arch / CachyOS / Manjaro, Debian / Ubuntu / Mint, Fedora, openSUSE**. L'installateur installe les
dépendances (après confirmation), ajoute l'application au menu, la commande `ambiluz` et une règle udev. Branchez la
bande LED et lancez **Ambiluz** depuis le menu.

Désinstallation : `curl -fsSL https://raw.githubusercontent.com/SrNoelll/skydimo-linux/main/install.sh | bash -s -- --uninstall`

## ✨ Fonctionnalités

- 🖥 **Synchro écran :** plein écran, moitié haute / basse / gauche / droite et **mode cinéma** ; détection automatique des
  bandes noires, lissage, saturation, gamma. Capture via **xdg-desktop-portal + PipeWire** (KDE Plasma, GNOME, Hyprland, Sway…) ou directement sous **X11**.
- 🎵 **Musique :** réagit au son du PC (ou au micro) : spectre, pulsation, VU-mètre, ondes, arc-en-ciel rythmé, basses.
- 🌈 **Flux :** arc-en-ciel, dégradé, aurore, vague, respiration, cycle de couleurs, scintillement, feu — 13 palettes.
- 🎨 **Couleur unie :** fixe, respiration, battement de cœur, bougie, clignotement.
- 🏇 **Chenillard :** course de chevaux, marquise, comète, scanner, blocs.
- 🔌 **Plug & play :** détection automatique du port et du **modèle**, reconnexion après débranchement ou mise en veille.
- 🛠 **Calibrage :** identification des côtés, balayage LED par LED, test RGB, sens, décalage, ordre des couleurs, balance des blancs.
- 🌍 **6 langues :** français, English, Español, 简体中文, 日本語, Русский.

## 🔦 Modèles compatibles

Bandes et barres Skydimo avec le contrôleur USB **CH340** (`1a86:7523`) : SK0121, SK0124, SK0127, SK0132, SK0134, SK0149,
SKA124/127/132/134, SK0L21/24/27/32/34, SK0201/0202/0204, SK0F01/F02, SK0402/0403.
Modèle non reconnu ? Utilisez une disposition personnalisée et [ouvrez une issue](https://github.com/SrNoelll/skydimo-linux/issues/new?template=new_model.yml).

## ⌨️ Ligne de commande

```bash
ambiluz --toggle           # allumer/éteindre (à associer à un raccourci clavier)
ambiluz --mode music       # sync | flow | mono | music | race
ambiluz --probe            # détecter la bande, son modèle et son nombre de LED
```

Projet indépendant et non officiel, sans lien avec Skydimo. Licence [GPL-3.0](../LICENSE). Si c'est utile, une ⭐ aide beaucoup !

<div align="center">

<img src="../ambiluz/icon.svg" width="110" alt="Ambiluz">

# Ambiluz — Skydimo 的 Linux 版

**为 Skydimo 显示器氛围灯打造的 Linux 应用。**
支持 Wayland 和 X11 的屏幕同步（类 Ambilight）、音乐律动、灯效和系统托盘，无需 Windows 官方软件。

[English](../README.md) · [Español](README.es.md) · **简体中文** · [日本語](README.ja.md) · [Русский](README.ru.md) · [Français](README.fr.md)

<img src="img/demo.gif" width="640" alt="Ambiluz 实时预览">

</div>

## ⚡ 一行安装

```bash
curl -fsSL https://raw.githubusercontent.com/SrNoelll/skydimo-linux/main/install.sh | bash
```

支持 **Arch / CachyOS / Manjaro、Debian / Ubuntu / Mint、Fedora、openSUSE**。安装程序会（先询问）安装依赖，
添加应用菜单项、`ambiluz` 命令以及 udev 规则。插入灯带后，从应用菜单打开 **Ambiluz** 即可。

卸载：`curl -fsSL https://raw.githubusercontent.com/SrNoelll/skydimo-linux/main/install.sh | bash -s -- --uninstall`

## ✨ 功能

- 🖥 **屏幕同步**：全屏、上/下/左/右半屏、**电影模式**；自动识别黑边、平滑、饱和度、伽马。通过 **xdg-desktop-portal + PipeWire**
  捕获（KDE Plasma、GNOME、Hyprland、Sway…），或直接在 **X11** 上捕获。
- 🎵 **音乐**：跟随电脑播放的声音（或麦克风）：频谱、脉冲、音量表、涟漪、节奏彩虹、低音。
- 🌈 **流光**：彩虹、渐变、极光、波浪、呼吸、颜色循环、闪烁、火焰，13 种调色板。
- 🎨 **单色**：常亮、呼吸、心跳、烛光、闪动。
- 🏇 **跑马灯**：赛马、跑马灯、彗星、扫描、色块。
- 🔌 **即插即用**：自动识别端口和**型号**，拔插后自动重连，支持睡眠唤醒。
- 🛠 **校准**：识别各边、逐灯扫描、RGB 测试、方向、偏移、颜色顺序、白平衡。
- 🌍 **6 种语言**：简体中文、English、Español、日本語、Русский、Français。

## 🔦 支持的型号

使用 **CH340** USB 串口控制器（`1a86:7523`）的 Skydimo 灯带与灯条：SK0121、SK0124、SK0127、SK0132、SK0134、SK0149、
SKA124/127/132/134、SK0L21/24/27/32/34、SK0201/0202/0204、SK0F01/F02、SK0402/0403。
型号未被识别？可使用自定义布局，并欢迎[提交 issue](https://github.com/SrNoelll/skydimo-linux/issues/new?template=new_model.yml)。

## ⌨️ 命令行

```bash
ambiluz --toggle           # 开/关（可绑定到快捷键）
ambiluz --mode music       # sync | flow | mono | music | race
ambiluz --probe            # 检测灯带型号和灯珠数
```

本项目为独立的非官方项目，与 Skydimo 无关。许可证：[GPL-3.0](../LICENSE)。觉得好用请点个 ⭐！

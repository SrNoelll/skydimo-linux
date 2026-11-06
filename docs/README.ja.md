<div align="center">

<img src="../ambiluz/icon.svg" width="110" alt="Ambiluz">

# Ambiluz — Skydimo for Linux

**Skydimo モニター用バックライトのための Linux アプリ。**
Wayland と X11 での画面同期（Ambilight 風）、音楽モード、エフェクト、システムトレイに対応。Windows 版アプリは不要です。

[English](../README.md) · [Español](README.es.md) · [简体中文](README.zh-CN.md) · **日本語** · [Русский](README.ru.md) · [Français](README.fr.md)

<img src="img/demo.gif" width="640" alt="Ambiluz のライブプレビュー">

</div>

## ⚡ インストール（1行）

```bash
curl -fsSL https://raw.githubusercontent.com/SrNoelll/skydimo-linux/main/install.sh | bash
```

**Arch / CachyOS / Manjaro、Debian / Ubuntu / Mint、Fedora、openSUSE** に対応。インストーラーが（確認のうえ）依存関係、
アプリメニュー、`ambiluz` コマンド、udev ルールを設定します。LED テープを接続し、メニューから **Ambiluz** を起動してください。

アンインストール：`curl -fsSL https://raw.githubusercontent.com/SrNoelll/skydimo-linux/main/install.sh | bash -s -- --uninstall`

## ✨ 機能

- 🖥 **画面同期**：全画面、上下左右の半分、**映画モード**。黒帯の自動検出、スムージング、彩度、ガンマ。
  **xdg-desktop-portal + PipeWire**（KDE Plasma、GNOME、Hyprland、Sway など）または **X11** で直接キャプチャ。
- 🎵 **音楽**：PC で再生中の音（またはマイク）に反応：スペクトラム、パルス、VU メーター、波紋、ビートレインボー、低音。
- 🌈 **フロー**：レインボー、グラデーション、オーロラ、ウェーブ、呼吸、カラーサイクル、きらめき、炎（13 パレット）。
- 🎨 **単色**：固定、呼吸、鼓動、ろうそく、点滅。
- 🏇 **流れる光**：競馬、マーキー、彗星、スキャナー、ブロック。
- 🔌 **プラグ＆プレイ**：ポートと**モデル**を自動検出、抜き差しやスリープ後も自動再接続。
- 🛠 **キャリブレーション**：辺の識別、LED を 1 つずつ点灯、RGB テスト、方向、オフセット、色の順序、ホワイトバランス。
- 🌍 **6 言語**：日本語、English、Español、简体中文、Русский、Français。

## 🔦 対応モデル

**CH340** USB シリアルコントローラー（`1a86:7523`）搭載の Skydimo 製品：SK0121、SK0124、SK0127、SK0132、SK0134、SK0149、
SKA124/127/132/134、SK0L21/24/27/32/34、SK0201/0202/0204、SK0F01/F02、SK0402/0403。
未対応のモデルはカスタムレイアウトで使用でき、[issue](https://github.com/SrNoelll/skydimo-linux/issues/new?template=new_model.yml) で追加をリクエストできます。

## ⌨️ コマンドライン

```bash
ambiluz --toggle           # オン/オフ（キーボードショートカットに割り当て可能）
ambiluz --mode music       # sync | flow | mono | music | race
ambiluz --probe            # LED テープのモデルと LED 数を表示
```

Skydimo とは関係のない非公式の独立プロジェクトです。ライセンス：[GPL-3.0](../LICENSE)。役に立ったら ⭐ をお願いします！

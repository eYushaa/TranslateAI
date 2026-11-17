<div align="center">

# 🌐 TranslateAI

### **No Barrier, No Border**

*Windows 10 & 11 向けに設計された、システム全体の AI 翻訳・画面 OCR・文章推敲アシスタント。*

[![Platform](https://img.shields.io/badge/Platform-Windows%2010%20%2F%2011-0078D6?logo=windows&logoColor=white)](https://microsoft.com/windows)
[![Release](https://img.shields.io/badge/Release-v1.0.1-success?logo=github)](https://github.com/eYushaa/AI-Translator/releases)
[![PySide6](https://img.shields.io/badge/GUI-PySide6%20%2F%20Qt-41CD52?logo=qt&logoColor=white)](https://www.qt.io/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](../LICENSE)

---

**[English](../README.md) • [Türkçe](README.tr.md) • [Español](README.es.md) • [Français](README.fr.md) • [Deutsch](README.de.md) • [Русский](README.ru.md) • [العربية](README.ar.md) • [עברית](README.he.md) • [简体中文](README.zh.md) • [日本語](README.ja.md) • [한국어](README.ko.md)**

---

</div>

## 🌟 概要

**TranslateAI** は、Windows システム上のあらゆる場所で高品質な AI 翻訳、内蔵 `.gguf` オフライン推論、画面切り取りによる文字認識（OCR）、文章のブラッシュアップ（推敲）をキーボードショートカットから直接呼び出せるモダンなユーティリティです。

Outlook でのメール作成、Slack や Discord でのチャット、VS Code でのプログラミング、ブラウザでの記事閲覧など、どんなアプリを使用していても作業を中断することなくシームレスに機能します。

> **「No Barrier, No Border」** — 言語の壁や国境を越え、デスクトップ上で高いプライバシーと自由なコミュニケーションを実現します。

---

## 🆕 v1.0.1 の新機能

- **🧠 内蔵 TranslateAI Engine（`.gguf` 実行 & コンテキスト自動拡張）：** アプリと同じディレクトリに `models/` フォルダーを自動作成し、`.gguf` モデルを 100% オフライン実行します。長文時に上限（既定 **10K**）まで**コンテキストを自動拡張（`4K → 8K → 16K → 50K`）**し、上限超過時は**動的コンテキスト短縮**を行います。
- **💬 コンテキスト認識翻訳（Context-Aware Translation）：** 直近の翻訳（既定で最新 5 件を 30 分間 RAM のみに保持）を参照として AI に渡し、会話全体で代名詞・固有名詞・専門用語・文体の一貫性を保ちます。
- **🔌 OpenAI Compatible プロバイダー：** ローカル／互換エンドポイントを **OpenAI Compatible** に統一し、スクロール矢印のない安定したモダンなタブデザインに刷新しました。
- **🇮🇱 ヘブライ語 UI & RTL レイアウト対応（`עברית`）：** アラビア語に加えてヘブライ語の UI ローカライズと右から左（RTL）表示を完全サポート（全 11 言語対応）。
- **🎨 UI・視認性の向上：** くっきりとしたベクターチェックマーク、言語選択欄の括弧表記の整理、各ショートカット下のグレーの補足説明を追加しました。
- **🏷️ TranslateAI への正式名称変更：** アプリ名称および実行ファイル（`TranslateAI.exe`）を **TranslateAI** に統一しました。

---

## 📥 ダウンロードとクイックスタート

Python のインストールやコマンドライン操作は不要です。

1. GitHub の **[Releases (リリース)](https://github.com/eYushaa/AI-Translator/releases)** ページを開きます。
2. **`TranslateAI-Setup.exe`** をダウンロードしてインストーラーを実行します。
3. セットアップ中に使いたい AI モデルを選択し、ダウンロードを完了させます。
4. さあ、**TranslateAI** が **Windows タスクトレイ** ですぐに使えるようになりました！

---

## ✨ 主な機能

### 🚀 1. システム全体のグローバルショートカット
- **`Alt + B` — その場で置き換え翻訳 (In-Place)：** 選択したテキストを直接翻訳後のテキストに置き換えます。
- **`Alt + N` — ポップアップ翻訳：** 原文を変更せず、カーソル横の美しいフローティングウィンドウに翻訳を表示します。
- **`Alt + O` — 画面切り取り & OCR 翻訳：** 画面上の画像や動画、PDF から文字の範囲をドラッグ選択し、瞬時に認識・翻訳します。
- **`Alt + M` — 言語クイック切り替え：** Spotlight 風の検索窓から目的の翻訳言語をすばやく切り替えます。
- **`Alt + V` — 文章の推敲と流暢さの向上：** 原文の言語のまま、より自然でプロフェッショナルな表現に書き直します。
- **`Alt + C` — スペル・文法チェック：** タイプミスや句読点、文法の間違いをその場で自動修正します。

---

### 📸 2. デュアル OCR エンジン（Windows ネイティブ & AI Vision）
- **高速・オフライン動作：** Windows 標準の `Windows.Media.Ocr` を直接利用し、オフラインでも瞬時にテキストを認識します。
- **AI Vision フォールバック：** 特殊なフォントや複雑な背景で検出できない場合、自動的に **Google Gemini Vision** が補助します。

---

### 🤖 3. 豊富な AI プロバイダー & 内蔵 GGUF エンジン
- **TranslateAI Engine（内蔵 `.gguf`）：** `models/` フォルダー内の `.gguf` モデルを外部サーバー不要で 100% オフライン実行。**コンテキスト自動拡張（`4K → 8K → 16K → 50K`）**、*プロバイダー → TranslateAI Engine* での最大上限設定（既定 **10K**）、および**動的コンテキスト短縮**に対応しています。
- **OpenAI Compatible (Ollama / LocalAI / vLLM)：** OpenAI 互換 API (`http://localhost:11434/v1`) により、完全オフラインで安全に利用可能。
- **LM Studio：** ローカルモデル環境と直接接続 (`http://localhost:1234/v1`)。
- **Google Gemini：** Gemini 3.8 Flash、Gemini 3.5 Flash-Lite、Gemini 4（Argon / Hydrogen / Carbon）による超高速・高精度のクラウド翻訳。
- **Google Translate：** API キー不要ですぐに利用可能。

---

## 📸 スクリーンショット

| 言語設定 & プロンプトカスタマイズ | 画面切り取り & OCR 設定 |
|:---:|:---:|
| ![言語設定](../docs/screenshots/1_languages.png) | ![OCR 設定](../docs/screenshots/2_ocr.png) |

| AI プロバイダー & 接続先 | グローバルショートカット一覧 |
|:---:|:---:|
| ![AI 設定](../docs/screenshots/3_providers.png) | ![ショートカット](../docs/screenshots/4_shortcuts.png) |

| 言語クイック切り替え (Alt+M) | フローティング翻訳ポップアップ (Alt+N) |
|:---:|:---:|
| ![クイック切り替え](../docs/screenshots/7_language_picker.png) | ![ポップアップ](../docs/screenshots/8_translation_popup.png) |

| 一般設定 & UI 言語バー | プライバシー & 履歴管理 |
|:---:|:---:|
| ![一般設定](../docs/screenshots/0_general.png) | ![プライバシー](../docs/screenshots/5_privacy.png) |

---

## ⌨️ ショートカット一覧

| ショートカット | 機能 | 説明 |
|:---|:---|:---|
| <kbd>Alt</kbd> + <kbd>B</kbd> | **その場で翻訳** | 選択中のテキストを直接翻訳結果に置き換えます。 |
| <kbd>Alt</kbd> + <kbd>N</kbd> | **ポップアップ翻訳** | 選択テキストの翻訳を小窓に表示します。 |
| <kbd>Alt</kbd> + <kbd>O</kbd> | **画面 OCR 翻訳** | 画面の文字を範囲選択して文字起こし＆翻訳します。 |
| <kbd>Alt</kbd> + <kbd>M</kbd> | **翻訳言語の変更** | 翻訳先言語のクイック選択メニューを開きます。 |
| <kbd>Alt</kbd> + <kbd>V</kbd> | **文章の推敲** | 文章をより自然で洗練された表現に改善します。 |
| <kbd>Alt</kbd> + <kbd>C</kbd> | **文法・スペル修正** | 誤字脱字や文法の間違いを修正します。 |

---

## 📄 ライセンス

本プロジェクトは [MIT ライセンス](../LICENSE) のもとで公開されています。

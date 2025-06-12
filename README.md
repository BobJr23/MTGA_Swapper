# MTGA Swapper 🎴🛠️  


![Python Version](https://img.shields.io/pypi/pyversions/realesrgan-ncnn-py)

Easily **edit or swap assets** in *Magic: The Gathering Arena*, including:  
🎨 Sleeves, 🧙‍♂️ Card Art, 🌄 Lands, 🧍 Avatars, 🪄 Emotes, 🐾 Pets, and more!

**✅ Fixed major bugs – fully working**

Report any issues in Feedback & Support



> 📢 Full explanation & community post on Reddit:  
> [MTG Arena Asset Editor/Extractor](https://www.reddit.com/r/MagicArena/comments/1avproc/mtg_arena_asset_editorextractor/)

---

## 📚 Table of Contents

- [🚀 Quick Start](#-quick-start)
- [⚠️ Disclaimer](#️-disclaimer)
- [🖼️ How to Use](#️-how-to-use)
  - [1. Select your MTGA database file](#1-select-your-mtga-database-file)
  - [2. Choose an export folder](#2-choose-an-export-folder)
  - [3. Browse and swap card art](#3-browse-and-swap-card-art)
  - [4. Swap custom land art](#4-swap-custom-land-art)
  - [5. Edit other assets](#5-edit-other-assets)
- [✨ Final In-Game Results](#-final-in-game-results)
- [💬 Feedback & Support](#-feedback--support)

---

## 🚀 Quick Start

1. **Install Python (≤ 3.12):**  
   👉 [Download from python.org](https://www.python.org/downloads/)

2. **Clone repository (or download and unzip source code):**
   ```bash
   git clone https://github.com/BobJr23/MTGA_Swapper.git
   ```

4. **Install dependencies:**  
   ```bash
   pip install -r requirements.txt
   ```

5. **Run the app:**  
   ```bash
   python main.py
   ```

> 🆕 **Now uses [FreeSimpleGUI](https://pypi.org/project/freesimplegui/)** instead of PySimpleGUI (discontinued).  
> Requirements updated – make sure to re-install.

---

## ⚠️ Disclaimer

- Use at your own risk.
- This is for educational purposes only.
- I'm **not responsible** for any issues with your device or account.  
- This tool may violate MTG Arena's TOS – this repo will be removed if requested.

---

## 🖼️ How to Use

### 1. Select your MTGA database file  
Locate your Arena install folder and choose the appropriate `.mtga` database file.

![Database Selection](https://github.com/BobJr23/MTGA_Swapper/assets/98911103/d76fb165-cb32-447a-a27b-70719b292c9c)

---

### 2. Choose an export folder  
Pick where you want exported game assets (images) to be saved.

---

### 3. Browse and swap card art  
Cards will appear in a list. Click one to preview the artwork and select a replacement. (If art shows up as green marks, press "Next in bundle")

![image](https://github.com/user-attachments/assets/cffc1252-8cfa-41f3-a04c-1942575d0627)

> 🔄 *Note:* "Change style" feature not yet implemented.

---

### 4. Swap custom land art  
To unlock custom lands:

- Set a **normal** land (ArtSize = 0) as Swap 1
- Set a **custom** land (ArtSize = 2) as Swap 2  
- Hit **Swap Arts**

![Swap Lands 1](https://github.com/user-attachments/assets/503891a7-a090-4992-85e1-e0e339ec8a30)
![image](https://github.com/user-attachments/assets/a20d06ba-e38e-4be4-929c-32d15ad539ff)
![image](https://github.com/user-attachments/assets/c5902f02-f52e-4223-ae19-67a0f92f2db3)

![image](https://github.com/user-attachments/assets/201a1fc7-259e-4271-a161-5990fce60667)
![image](https://github.com/user-attachments/assets/f0c72a34-7922-45d3-a69d-3a006bc35487)

---

### 5. Edit other assets  
Change avatars, sleeves, and more using the same interface.

![Avatar Editing](https://github.com/BobJr23/MTGA_Swapper/assets/98911103/53afa37a-ca57-4a84-9b24-3a91c6becc86)

---
   If you want to export the font files in ttf format, run
   ```bash
   python asset_viewer.py
   ```

---

## ✨ Final In-Game Results

Get creative – make MTGA look how *you* want!

![Result 1](https://github.com/BobJr23/MTGA_Swapper/assets/98911103/d72bcdec-2f6b-4804-89aa-4d42634aedcc)
![Result 2](https://github.com/BobJr23/MTGA_Swapper/assets/98911103/8e56bd7e-c6c5-499f-a1c3-37e6702dacab)  
![Result 3](https://github.com/BobJr23/MTGA_Swapper/assets/98911103/2e023d86-0b2d-4515-bc1e-9b9278ec6f00)  
![Result 4](https://github.com/BobJr23/MTGA_Swapper/assets/98911103/115e8e66-85c2-4f51-af9d-f9cb46482b8b)

---

## 💬 Feedback & Support

Got questions or ideas? Reach out on Discord:  
**`_bobjr_`**

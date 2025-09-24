# MTGA Swapper 🎴🛠️  


![Python Version](https://img.shields.io/pypi/pyversions/realesrgan-ncnn-py)

Easily **edit, swap, and export assets** in *Magic: The Gathering Arena*, including:  
🎨 Sleeves, 🧙‍♂️ Card Art, 🌄 Lands, 🧍 Avatars, 🪄 Emotes, 🐾 Pets, and more!


Unlock any card styles in the game, including parallax and speical event styles. (See table of contents section 11)

**Cool New Features:**

- You can unlock mass unlock parallax styles for any number of cards with one click
- You can export your changes to a file and then load it after updates or share it for others to use.
- You can unlock any unique card style/border. See [11. Unlock card styles](#11-unlock-card-styles) for reference

**NEW: exe file in [releases](https://github.com/BobJr23/MTGA_Swapper/releases)**


Report any issues in Feedback & Support


---

## 📚 Table of Contents

- [🚀 Quick Start](#-quick-start)
- [⚠️ Disclaimer](#️-disclaimer)
- [🖼️ How to Use](#️-how-to-use)
  - [1. Select your MTGA database file](#1-select-your-mtga-database-file)
  - [2. Choose an export folder](#2-choose-an-export-folder)
  - [3. Browse card directory](#3-browse-card-directory)
  - [4. Edit game assets](#4-edit-game-assets)
  - [5. Upscaling Art](#5-upscaling-art)
  - [6. Set Aspect Ratio](#6-set-aspect-ratio)
  - [7. Swap custom land art](#7-swap-custom-land-art)
  - [8. Edit other assets](#8-edit-other-assets)
  - [9. Import Decklists](#9-import-decklists)
  - [10. Export Fonts](#10-export-fonts)
  - [11. Unlock card styles](#11-unlock-card-styles)
  - [12. Export your changes](#12-export-your-changes)
- [✨ Final In-Game Results](#-final-in-game-results)
- [💬 Feedback & Support](#-feedback--support)

---

## 🚀 Quick Start


# Simple Install
You can download the .exe file from releases [here](https://github.com/BobJr23/MTGA_Swapper/releases)


**OR**

# Python Method

Check if Git is installed with 

```bash
git --version
```

If not,
[Install Git here](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)



1. **Install Python (Recommended: 3.11; Compatible: ≤ 3.12)**  
   👉 [Download Python](https://www.python.org/downloads/)

2. **(Recommended) Install [`uv`](https://github.com/astral-sh/uv) – a fast Python package and environment manager:**

   - **Windows:**
     ```powershell
     powershell -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
     ```

   - **Mac/Linux:**
     ```bash
     curl -LsSf https://astral.sh/uv/install.sh | sh
     ```

3. **Clone this repository (or download and unzip the source):**
   ```bash
   git clone https://github.com/BobJr23/MTGA_Swapper.git
   ```

   ```bash
   cd MTGA_Swapper
   ```

4. **(Recommended) Create a Python 3.11 virtual environment with `uv`:**
   ```bash
   uv venv --python 3.11
   ```

   ```bash
   .venv\Scripts\activate
   ```

5. **Install required dependencies:**
   ```bash
   uv pip install -r requirements.txt
   ```

   > Use requirements_noupscale.txt if you don't care about upscaling the images (saves space and time)

6. **Run the application:**
   ```bash
   uv run main.py
   ```

---

## ⚠️ Disclaimer

- Your opponents do not see your edits, this is only client-side
- Use at your own risk.
- This is for educational purposes only.
- I'm **not responsible** for any issues with your device or account.  
- This tool may violate MTG Arena's TOS – this repo will be removed if requested.

---

## 🖼️ How to Use

### 1. Select your MTGA database file  
Locate your Arena install folder and choose the appropriate `Raw_CardDatabase... .mtga` database file.

**(Default installation path is ```C:\Program Files (x86)\Wizards of the Coast```)**

or ```C:\Program Files (x86)\Steam``` 

or ```C:\Program Files\Epic Games``` 

depending on where you installed MTG Arena from 

![Database Selection](https://github.com/BobJr23/MTGA_Swapper/assets/98911103/d76fb165-cb32-447a-a27b-70719b292c9c)



---

### 2. Choose an export folder  
Pick where you want exported game assets (images) to be saved.

---

### 3. Browse card directory
Cards will appear in a list. Click one to preview the artwork and export the image with the Save button. (If art shows up as green marks, press "Next in bundle")

![image](https://github.com/user-attachments/assets/08688897-5dad-4128-8190-149aea42a9fe)


![image](https://github.com/user-attachments/assets/e1f971b0-30cf-471b-ba86-fbfe161f8921)


---

### 4. Edit game assets

After you have made edits to the card you would like, click on Change image, then select your new image file.

---

### 5. Upscaling Art
To increase image quality, press the upscale button (may take a few seconds). 

It is recommended to upscale the image **before** changing the aspect ratio to achieve the highest quality.


---

### 6. Set Aspect Ratio
Click the set aspect ratio button after opening the image if you would like to export them in their proper aspect ratio. 
- Note: If you would like to edit the asset in-game, don't change the aspect ratio, as Arena will change the ratio for you.

The aspect ratios are 

- 11:8 for most cards
- 3:4 for planeswalkers and larger art cards (Ex. Eldrazi)
- 4:3 for battles

---

### 7. Swap custom land art  
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

### 8. Edit other assets  
Change avatars, sleeves, and more using the same interface.

![Avatar Editing](https://github.com/BobJr23/MTGA_Swapper/assets/98911103/53afa37a-ca57-4a84-9b24-3a91c6becc86)


---

### 9. Import Decklists 

- You can paste MTG Arena decklists or .txt files to filter certain cards you use. Make sure the Use Decklist toggle is checked after importing
  
![image](https://github.com/user-attachments/assets/75dbd661-48af-4eca-995a-ff0ff27d2df5)



### 10. Export Fonts 

---
   If you want to export the font files in ttf format, there is now a button in the App's main menu
---

### 11. Unlock Card Styles


   <img width="1421" height="321" alt="image" src="https://github.com/user-attachments/assets/f64c8163-aba0-4d6f-822c-9af798ac71fa" />
   
See the [list of working tags](https://github.com/BobJr23/MTGA_Swapper/blob/main/tags.md)

1696804317 is the parallax style most cards have for 200-1200 gems which show the card "moving" and being borderless
   
---

### 12. Export Your Changes

After every game update, you may notice that your changes disappear. This is fine, just press the "Export Changes Preset" button on the main page to save your changes, and then "Load Changes Preset" to automatically make your changes.

## ✨ Final In-Game Results

Get creative – make MTGA look how *you* want!

![Result 1](https://github.com/BobJr23/MTGA_Swapper/assets/98911103/d72bcdec-2f6b-4804-89aa-4d42634aedcc)
![Result 2](https://github.com/BobJr23/MTGA_Swapper/assets/98911103/8e56bd7e-c6c5-499f-a1c3-37e6702dacab)  
![Result 4](https://github.com/BobJr23/MTGA_Swapper/assets/98911103/115e8e66-85c2-4f51-af9d-f9cb46482b8b)

---

## 💬 Feedback & Support

Got questions or ideas? Reach out on Discord:  
**`_bobjr_`**

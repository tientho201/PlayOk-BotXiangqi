# 🏆 Real-Time AI Xiangqi Assistant (PlayOK AI Xiangqi Coach)

Welcome to **PlayOK AI Xiangqi Coach** - the ultimate real-time Chinese Chess (Xiangqi) coaching assistant!

This application uses **Computer Vision (OpenCV)** to automatically synchronize the board state from your web browser (PlayOK) to a local virtual board widget, leveraging the power of the **Pikafish engine (ELO 3000+)** to calculate and overlay the best moves as neon arrows directly on your screen in real-time.

> [!TIP]
> This application runs as a lightweight, transparent overlay on top of your screen. It does NOT modify the code or interact with the web browser's DOM, ensuring absolute safety for your PlayOK account.

---

## ✨ Features Checklist

* 🔄 **Real-Time High-Speed Sync**: Instantly detects move changes on the browser using pixel-diff tracking (runs at 100ms intervals / 10 FPS).
* 🤖 **Powerhouse AI Engine**: Connects seamlessly with the Pikafish chess engine via UCI to calculate optimal moves up to your preferred search depth.
* 🎯 **Dynamic Visual Overlay**: Draws beautiful neon arrows directly on top of your web browser as soon as it is your turn.
* 🛡️ **Interactive Correction (Ground Truth)**: If the OCR scanner misrecognizes a piece, you can easily drag-and-drop pieces or use the **Piece Palette** on the sidebar to correct the local state manually.
* 🔄 **Auto-Perspective Detection**: Automatically detects whether you are playing as Red or Black and flips the board 180 degrees accordingly (always keeping your pieces at the bottom).
* 🔀 **Universal Character Support (Traditional & Simplified)**: The intelligent OCR engine robustly recognizes both Traditional (`車`, `馬`, `將`,...) and Simplified (`车`, `马`, `将`,...) character sets across different PlayOK board styles and themes.
* 👁️ **User-Only Suggestions**: Only displays bestmove overlay arrows during your active turn to avoid distraction. During the opponent's turn, it displays a neat *"Opponent's turn..."* status.

---

## 🛠️ Setup & Installation Guide (For New Users)

### Step 1: Download the Source Code
Download this repository as a `.zip` file and extract it to a directory on your computer, or clone it using Git:
```bash
git clone https://github.com/tientho201/PlayOk-BotXiangqi.git
```

### Step 2: Install Python & Libraries
1. Download and install [Python 3.11+](https://www.python.org/downloads/) on Windows (make sure to check **"Add Python to PATH"** during installation).
2. Open CMD or PowerShell in the project root directory and run the following command to install the required libraries:
   ```bash
   pip install -r requirements.txt
   ```

### Step 3: Download the Pikafish Engine Binary
Because the engine executable is large and platform-dependent, you must obtain it separately:
1. Download the latest Pikafish release for Windows from the official repository: [Pikafish Releases](https://github.com/official-pikafish/pikafish/releases) (or download any standard Xiangqi UCI-compatible engine).
2. Create a folder named `engine` in the root directory of the project (if it doesn't already exist).
3. Rename the downloaded engine binary file to `pikafish.exe` and place it inside the `engine/` directory.
   * *The correct file path structure should be:* `Bot-PlayOK/engine/pikafish.exe`

---

## 🚀 Step-by-Step Operating Guide

### Step 1: Start the Coach Application
Open PowerShell or CMD in the project root directory and execute:
```powershell
python .\main.py
```

### Step 2: Calibrate and Frame the Web Board
1. Open your browser and navigate to your active Xiangqi match on PlayOK.
2. In the Coach desktop application, click the **"Chọn Bàn Cờ"** (Select Board) button.
3. Move your cursor to the browser, **left-click and drag a selection box to frame the entire chess board** (including its outer borders).
4. *(Optional)* Fine-tune the **"Căn lề bàn cờ (Grid Margin)"** slider on the right sidebar so the blue alignment circles overlay exactly on the centers of the board cells.

### Step 3: Synchronize the Initial State
* Click the **"Đồng Bộ (Sync 1L)"** (Single-shot Sync) button to scan and load the current piece layout.
* **Manual Adjustments (If any piece is scanned incorrectly/missing)**:
  * Select the desired piece from the **Piece Palette Card** on the right sidebar (the selected button will glow with a neon border).
  * Click on the target cell on the local virtual grid to instantly place it.
  * To move pieces normally, select the teal **"Di Chuyển"** (Move) button. To remove a piece, select the red **"Tẩy/Xóa"** (Eraser) button.

### Step 4: Start Tracking & Receive AI Suggestions
* Click the **"Bắt Đầu Theo Dõi"** (Start Tracking) button. The application status badge will turn green (**"Đang Theo Dõi"**).
* From now on, any move played by you or your opponent on the web browser will automatically synchronize to the local app.
* When it is your turn to move, the system will instantly calculate the best move and overlay a **Neon Arrow** directly on top of your web browser to guide your play!

---

## 💡 Troubleshooting & Out-of-Sync Recovery

> [!IMPORTANT]
> **How to recover if the board goes out-of-sync or the active turn gets swapped:**
> 1. Click the **"Force Resync"** button on the local app. The tracking status will change to orange (**"Tạm Dừng Sync"**).
> 2. Use the **Piece Palette** or **Drag-and-Drop** pieces to adjust the local board so it matches the web browser 100%.
> 3. Set the correct active color under the *"Lượt Đi"* (Active Turn) card (Red or Black).
> 4. Click **"Bắt Đầu Theo Dõi"** (Start Tracking) again. The system will capture a new baseline screenshot and resume tracking smoothly!

---

Enjoy your games and play like a master with Pikafish! 👑

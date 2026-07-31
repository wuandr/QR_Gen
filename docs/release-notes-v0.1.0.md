Type a web address, pick how it should look, and save the image. Every code is
checked to make sure it still scans. The interface is available in English and
繁體中文.

*繁體中文安裝說明請往下捲動。*

---

# English

## Which file do I download?

| Your computer | File |
| --- | --- |
| Mac (Apple silicon — M1 or newer) | `qr-generator-macos-arm64.zip` |
| Windows (64-bit) | `qr-generator-windows-x64.zip` |
| Linux (64-bit) | `qr-generator-linux-x64.zip` |

Intel Macs are not covered by this build.

## Mac

1. Download the zip and double-click it to unpack `QR_Generator.app`.
2. Drag the app to your Applications folder (optional, but tidier).
3. **Right-click the app and choose Open**, then click Open again in the dialog
   that appears.

Double-clicking the app the first time will not work. This app isn't signed with
an Apple developer certificate, so macOS blocks it by default — right-click →
Open is how you tell macOS you trust it. You only need to do this once; after
that it opens normally.

If macOS says the app is damaged or can't be opened, open Terminal, run this,
then try again:

```bash
xattr -dr com.apple.quarantine /Applications/QR_Generator.app
```

Adjust the path if you kept the app somewhere other than Applications.

## Windows

1. **Make a new empty folder first, and extract the zip into it.** There is no
   folder inside the zip, so extracting straight into Downloads will scatter
   loose files everywhere.
2. Open that folder and run `QR_Generator.exe`.
3. Windows will show a blue "Windows protected your PC" box. Click
   **More info**, then **Run anyway**.

That warning appears because the app isn't code-signed. Keep the whole folder
together — the `.exe` needs the files sitting next to it.

## Linux

1. Unzip the download. You'll get a `QR_Generator` folder.
2. Run it:

   ```bash
   ./QR_Generator/QR_Generator
   ```

3. If nothing happens, make it executable and try again:

   ```bash
   chmod +x QR_Generator/QR_Generator
   ```

## Using it

Type or paste a web address and the code appears as you type. Pick a size, a
file type (PNG, JPEG, or SVG), and an appearance style, or drop an image into
the middle as a logo. Then **Save image**.

Switch between English and 繁體中文 from the picker at the top right, or the
Language menu. Your choice is remembered.

Prefer to run from source? See the
[README](https://github.com/wuandr/QR_Gen#setup).

---

# 繁體中文

輸入網址、選擇外觀，然後儲存圖片。每個 QR Code 都會經過檢查，確認可以掃描。
介面支援 English 與繁體中文。

## 我該下載哪一個檔案？

| 你的電腦 | 檔案 |
| --- | --- |
| Mac（Apple 晶片，M1 以上） | `qr-generator-macos-arm64.zip` |
| Windows（64 位元） | `qr-generator-windows-x64.zip` |
| Linux（64 位元） | `qr-generator-linux-x64.zip` |

這個版本不支援 Intel 處理器的 Mac。

## Mac

1. 下載 zip 檔後點兩下解壓縮，會得到 `QR_Generator.app`。
2. 可以把它拖到「應用程式」資料夾（非必要，但比較整齊）。
3. **在 App 上按右鍵，選擇「打開」**，然後在跳出的對話框中再按一次「打開」。

第一次直接點兩下是打不開的。這個 App 沒有經過 Apple 開發者簽章，macOS 預設會
擋下來，而按右鍵選「打開」就是告訴 macOS 你信任它。這個步驟只需要做一次，之後
就能正常開啟。

如果 macOS 顯示 App 已損毀或無法打開，請開啟「終端機」執行以下指令，然後再試
一次：

```bash
xattr -dr com.apple.quarantine /Applications/QR_Generator.app
```

如果 App 放在「應用程式」以外的位置，請自行調整路徑。

## Windows

1. **請先建立一個新的空資料夾，再把 zip 解壓縮到裡面。** 這個 zip 檔裡面沒有
   資料夾，直接解壓縮到「下載」會把檔案散落一地。
2. 打開該資料夾，執行 `QR_Generator.exe`。
3. Windows 會跳出藍色的「Windows 已保護您的電腦」視窗。請點
   **「其他資訊」**，再點 **「仍要執行」**。

出現這個警告是因為程式沒有經過簽章，屬於正常現象。請保持整個資料夾完整，
`.exe` 需要旁邊的檔案才能執行。

## Linux

1. 解壓縮後會得到一個 `QR_Generator` 資料夾。
2. 執行：

   ```bash
   ./QR_Generator/QR_Generator
   ```

3. 如果沒有反應，請加上執行權限後再試一次：

   ```bash
   chmod +x QR_Generator/QR_Generator
   ```

## 開始使用

輸入或貼上網址，QR Code 會即時顯示。你可以選擇尺寸、檔案格式（PNG、JPEG 或
SVG）與外觀樣式，也可以在中央加上圖片作為標誌，然後按 **「儲存圖片」**。

視窗右上角的語言選單，或功能表中的「語言」，都可以切換 English 與繁體中文，
你的選擇會被記住。

想從原始碼執行嗎？請參考
[README](https://github.com/wuandr/QR_Gen#setup)。

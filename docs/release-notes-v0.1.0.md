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
2. Drag the app into your Applications folder.
3. Double-click the app. macOS will refuse to open it and say it can't verify
   the developer. **This is expected** — click **Done**.
4. Open **System Settings → Privacy & Security** and scroll down to the
   **Security** section. There'll be a line saying QR_Generator was blocked,
   with an **Open Anyway** button. Click it.
5. Confirm with your password or Touch ID.

After that the app opens normally by double-clicking, like anything else. You
only go through this once.

**Do step 3 first.** The Open Anyway button doesn't appear in System Settings
until macOS has blocked the app at least once — go looking for it beforehand and
the Security section will be empty.

This happens because the app isn't signed with a paid Apple developer
certificate, so macOS treats it as unverified rather than trusted.

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
2. 把它拖到「應用程式」資料夾。
3. 點兩下打開 App。macOS 會拒絕開啟，並顯示無法驗證開發者的訊息。
   **這是正常的**，請按 **「完成」**。
4. 打開 **「系統設定」→「隱私權與安全性」**，往下捲到 **「安全性」** 區塊，
   會看到一行說明 QR_Generator 已被阻擋，旁邊有 **「仍要打開」** 按鈕，請點它。
5. 用密碼或 Touch ID 確認。

完成後，之後就能像一般 App 一樣點兩下直接開啟。這個步驟只需要做一次。

**請務必先做步驟 3。** 一定要先試著打開 App、被 macOS 擋下來之後，「系統設定」
裡才會出現「仍要打開」的按鈕；如果先去「系統設定」找，「安全性」區塊會是空的。

會這樣是因為這個 App 沒有經過 Apple 付費開發者簽章，macOS 會將它視為未經驗證
的軟體。

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

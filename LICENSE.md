# 授權條款

本專案由多個開源元件組合而成，各元件採用不同授權。

## 快速說明

- **本程式可自由使用、修改和分發**，但必須遵守內含元件的授權條款
- **如計畫商業使用或修改發佈，請務必閱讀下列詳細授權條款**

---

## 各元件授權詳情

### 1. FFmpeg（ffmpeg.exe, ffprobe.exe, ffplay.exe 與相關 DLL）

**授權條款**：LGPL v2.1+ 或 GPL v2+（取決於編譯配置）

**詳細授權文本**：見 `licenses/FFmpeg-LICENSE.txt`

**使用限制**：
- 如使用 LGPL 版本，可在專有應用中使用，但需公開所有修改
- 如使用 GPL 版本，衍生程式也須開源並採用相同授權
- 必須保留原著作權聲明

**建議**：若計劃商業發佈，建議確認使用的 FFmpeg 編譯版本及其授權方式。

---

### 2. Noto Sans TC（NotoSansTC-VF.ttf）

**授權條款**：SIL Open Font License 1.1

**詳細授權文本**：見 `licenses/NotoSansTC-LICENSE.txt`

**使用限制**：
- 可自由使用、修改和分發
- 修改後須改名字型
- 不可單獨販售字型檔案本身

---

### 3. PyQt5

**授權條款**：GPL v3 或商業授權（Riverbank Computing）

**使用限制**：
- 開源使用：需採用 GPL v3 授權
- 商業使用：需購買商業授權

---

### 4. PyInstaller

**授權條款**：GPL v2 with PyInstaller Exception

**限制**：允許打包商業程式，但衍生編譯器仍需遵守 GPL

---

### 5. Pillow（PIL）

**授權條款**：HPND License（Historical Permission Notice and Disclaimer）

**使用限制**：相對寬鬆，可自由使用和修改

---

## 使用本程式的方式與對應授權

### 情況 A：個人或非商業使用

✅ **完全允許**，無需額外動作。

- 下載並使用編譯好的 exe
- 根據 FFmpeg 授權條款自由使用
- 無需簽署或購買額外授權

---

### 情況 B：修改程式後自行使用

✅ **允許**，需遵守以下條件：

1. 保留所有原始著作權聲明和授權文本
2. 明確標示修改內容
3. 如修改後發佈，需採用相同授權（複製 `licenses/` 資料夾）

---

### 情況 C：修改後公開發佈（開源）

✅ **允許**，需遵守以下條件：

1. 選擇相容的開源授權（建議 GPL v3 或 LGPL v2.1+）
2. 公開所有原始碼
3. 保留所有授權文本和著作權聲明
4. 本 LICENSE.md 和 CHANGELOG.md 應包含在發佈物中

**推薦做法**：
- 在 GitHub 倉庫根目錄放置 LICENSE 檔案
- 在 README.md 中註明授權方式
- 保留 `licenses/` 資料夾與各元件授權文本

---

### 情況 D：商業發佈（編譯 exe）

⚠️ **需謹慎處理**，取決於 FFmpeg 版本：

**如使用 LGPL FFmpeg**：
- ✅ 可發佈專有 exe
- ⚠️ 需公開對 FFmpeg 的修改（如有）
- ⚠️ 使用者應能自行重新連接 FFmpeg

**如使用 GPL FFmpeg**：
- ❌ 不可發佈閉源 exe
- ✅ 必須開源衍生程式並採用 GPL v3+

**PyQt5 商業授權**：
- 如使用 PyQt5，需購買商業授權（除非衍生程式採用 GPL）

**建議**：
1. 確認編譯的 FFmpeg 版本及授權方式
2. 諮詢律師確認商業使用合規性
3. 在程式內或隨附檔案中清楚標示授權資訊

---

## 如何包含授權聲明

在發佈程式時，應包含以下內容：

```
本程式使用以下開源元件：

- FFmpeg（LGPL / GPL）: https://ffmpeg.org/
- Noto Sans TC（SIL OFL）: https://fonts.google.com/noto/specimen/Noto+Sans+TC
- PyQt5（GPL v3）: https://www.riverbankcomputing.com/software/pyqt/
- PyInstaller（GPL v2 with Exception）: https://pyinstaller.org/
- Pillow（HPND）: https://python-pillow.org/

詳見程式資料夾內 licenses/ 中的授權文本。
```

---

## 版權持有人聲明

本程式由 Kent Chang 於 2025-2026 年開發。

原始碼、UI 設計與相關文檔著作權歸開發者所有，衍生物須遵守本授權條款及內含元件授權。

---

## 免責聲明

本程式「依現狀」提供，無任何明示或暗示的擔保。開發者不對任何直接、間接、偶然或後果性損害負責，包括但不限於：

- 資料遺失
- 業務中斷
- 利潤損失

使用者自行承擔使用本程式的所有風險。

---

## 如有疑問

若對授權條款或使用限制有疑問，請：

1. 閱讀 `licenses/` 資料夾內的詳細授權文本
2. 查閱各元件的官方文檔
3. 聯絡 Kent Chang：kentxchang@gmail.com
4. 視商業情況，諮詢專業法律顧問

---

**最後更新**：2026-05-12

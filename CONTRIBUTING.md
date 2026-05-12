# 貢獻指南（Contributing Guide）

感謝你對本專案的興趣！歡迎透過報告問題、提交代碼或改進文檔來貢獻。

---

## 🎯 快速開始

### 報告 Bug

1. 在 [Issues](../../issues) 中搜尋是否已有相同報告
2. 如無，點擊 **New Issue** 並提供以下資訊：
   - **標題**：簡潔描述問題
   - **版本**：使用的程式版本
   - **複現步驟**：詳細步驟
   - **預期行為**：應該發生什麼
   - **實際行為**：實際發生什麼
   - **系統環境**：Windows 版本、Python 版本（如自行執行）
   - **附件**：截圖或錯誤訊息

**範例**：
```
標題：匯出影片時出現「無法讀取素材」錯誤

版本：V5.2

複現步驟：
1. 開啟程式
2. 匯入路徑為 C:\Users\Test\Desktop\video.mp4 的影片
3. 點擊「匯出影片」
4. 出現錯誤

預期行為：應正常生成 output_video.mp4

實際行為：彈出錯誤對話框
```

---

### 提出功能建議

1. 在 [Issues](../../issues) 中點擊 **New Issue**
2. 選擇 **Feature Request** 範本（如有）
3. 詳細說明：
   - 你期望的功能
   - 為什麼需要這個功能
   - 如何使用這個功能
   - 有無替代解決方案

**範例**：
```
標題：新增批量匯出功能

說明：
希望能同時處理多個專案檔（.json），一次匯出多個影片，
而不是逐個打開專案檔匯出。

使用場景：
製作系列影片時，每集是一個獨立專案，
現在需要一個個匯出很耗時。
```

---

## 👨‍💻 提交代碼

### 1. Fork 與 Clone

```bash
# Fork 此倉庫到你的 GitHub 帳號

# Clone 你的 Fork
git clone https://github.com/YOUR_USERNAME/Pic2Video_tools_V5.git
cd Pic2Video_tools_V5

# 新增 upstream 遠端
git remote add upstream https://github.com/original-owner/Pic2Video_tools_V5.git
```

### 2. 建立功能分支

```bash
# 更新到最新主分支
git fetch upstream
git checkout main
git merge upstream/main

# 從 main 建立新分支
git checkout -b feature/your-feature-name
```

**分支命名慣例**：
- `feature/description` - 新功能
- `fix/description` - 修復 bug
- `docs/description` - 文檔改進
- `refactor/description` - 代碼重構

### 3. 安裝開發環境

```bash
# 建立虛擬環境（推薦）
python -m venv venv

# 啟動虛擬環境
# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# 或 cmd:
venv\Scripts\activate.bat

# 安裝依賴
pip install -r requirements.txt

# 安裝開發工具（可選）
pip install pylint pytest black
```

### 4. 修改代碼

- 遵循現有代碼風格
- 添加必要的註解和文檔字串
- 避免不必要的大規模重構（應先開 Issue 討論）

**代碼風格指引**：
- 使用 4 空格縮進（不用 Tab）
- 變數名使用英文小寫，用底線分隔（snake_case）
- 類名使用帕斯卡命名法（PascalCase）
- 單行最長 100 字元
- 為複雜邏輯添加註解

### 5. 測試

在本地測試你的修改：

```bash
# 執行程式
python 多功能圖片影音製作器V5.py

# 進行手動測試
# - 開啟/保存專案
# - 匯入素材
# - 測試修改的功能
# - 匯出影片確保正常
```

### 6. 提交代碼

```bash
# 檢查修改
git status
git diff

# 添加修改
git add .

# 提交
git commit -m "描述你的修改"
```

**提交信息格式**（推薦）：
```
簡潔標題（50 字以內）

詳細說明（可選）：
- 修改了什麼
- 為什麼修改
- 如何測試

參考 Issue：#123
```

**例子**：
```
修復：字幕位置設定在某些解析度下不正確

問題：在 4K 解析度下，「置中」字幕位置未居中

修複：調整字幕計算邏輯以相對解析度，
而非使用絕對像素值

測試：
- 480P、720P、1080P、2K、4K 解析度都已測試
- 「下方」與「置中」位置設定都正確

修復 #456
```

### 7. 推送與提交 Pull Request

```bash
# 推送到你的 Fork
git push origin feature/your-feature-name

# 在 GitHub 上開啟 Pull Request
# 填寫 PR 模版（如有）
```

**Pull Request 檢查清單**：
- [ ] 標題清楚簡潔
- [ ] 說明修改內容和原因
- [ ] 參考相關 Issue（如有）：`Closes #123`
- [ ] 代碼已在本地測試
- [ ] 無明顯衝突
- [ ] 提交信息清楚

---

## 📝 改進文檔

文檔改進同樣歡迎！包括：

- 修正錯別字或格式錯誤
- 改進 README 的清晰度
- 補充常見問題解答
- 翻譯為其他語言

**流程同上，但改動會更快被合併**。

---

## 📋 審核流程

1. **自動檢查**（如設定）：程式碼風格、測試是否通過
2. **代碼審核**：維護者檢查邏輯、風格、設計
3. **反饋**：可能需要修改或補充
4. **合併**：通過審核後合併到主分支

---

## ⚖️ 授權與著作權

提交代碼即表示你同意在本專案的授權條款（見 `LICENSE.md`）下使用你的貢獻。

---

## 💡 開發建議

### 常見修改場景

**新增轉場效果**：
```python
# 在 多功能圖片影音製作器V5.py 中搜尋 TRANSITION_EFFECTS
TRANSITION_EFFECTS = [
    "fade",
    "your_new_effect",  # 新增
    ...
]
```

**修改 UI 配置**：
UI 使用 PyQt5，主要佈局在 `__init_ui()` 方法中。

**調試 FFmpeg 命令**：
程式生成的 ffmpeg 命令會在控制台輸出（若以 Python 直接執行），
方便診斷編碼或合成問題。

---

## 🐛 已知限制與 TODO

- 路徑包含中文字時無法正常使用（ffmpeg 限制）
- 不支援實時預覽（性能考量）
- GPU 加速未實現

如有興趣改進，歡迎討論！

---

## 问卷與反饋

完成貢獻後，可以：

1. 參與 Issue 討論
2. 提交建議或反饋
3. 幫助測試新功能

---

## 聯絡方式

- GitHub Issues：[提交問題](../../issues)
- Email：kentxchang@gmail.com

感謝你的貢獻！🎉


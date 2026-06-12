# 更新日誌

本專案的所有重大變更都會記錄在這個檔案。

## [Unreleased] - 2026-06-12

卡片資訊豐富度增強。

### 新增

- **IG 短影音次要按鈕**：每張推薦卡片的 footer 在「帶我去」下方新增
  「🎬 看 IG 短影音」secondary 按鈕。點擊後經由 redirect tracker 跳轉至
  Instagram explore search（以店家名稱為關鍵字），同時記錄 `ig_click` 事件
  供後續分析。
- 連結為即時組成，不需要新資料表或人工策展對照表；店名取自 `push_logs.place_name`，
  IG URL 模板若 Instagram 改路徑只需動 `routers/redirect.py` 一行。

### 技術細節

- `services/tracking.py`：新增 `ig_search_url_for(push_log_id)`，沿用既有
  HMAC 簽章。
- `routers/redirect.py`：新增 `action == "ig"` 分支，redirect 至
  `https://www.instagram.com/explore/search/keyword/?q={place_name}` 並寫入
  `ig_click` 事件。與 `navigate` 分支不同的是不呼叫 `mark_accepted`——
  點 IG 不代表用戶要去這家，避免污染「接受率」訊號。
- `flex_messages/daily_push.py`：footer contents 由 2 個元素改為 3 個
  （帶我去 / IG 短影音 / 不要再推這家）。

## [Unreleased] - 2026-06-08

第二輪整合更新：簡化 Onboard、改為三家 carousel、新增重設位置入口、加入宵夜時段，
並把先前的單卡 swap 機制改寫為「換一批」批次模式。核心架構（FastAPI + APScheduler
+ SQLite）、推播時段（06:30 / 11:30 / 17:30）、每週快報排程（週一 08:00）、Adhoc
臨時搜索、redirect tracker、天氣感知、時段－餐廳類型加權映射皆維持不變。

### 新增

- **Onboard 後立即推薦**：用戶傳完唯一位置後，回覆「設定完成！先幫你選一家——」
  並立刻推送一組三家餐廳的 carousel；消滅 onboard 後的空窗期。
- **宵夜時段**：依當下時段判斷推薦類型，新增 20:00 - 06:00 → `supper`，時段標籤
  改為「🌙 肚子餓了？」，篩選邏輯沿用 dinner。對應的 hour → meal 映射也套用到
  adhoc 與 onboard 後的立即推薦。
- **三家 carousel + ⭐ 首選標記**：每次推播改為三張卡片（左右滑動），加權排序中
  分數最高者的時段標籤加上「⭐ 首選」。社交證明、擴展半徑提示按既有規則套用。
- **「換一批」控制卡片**：carousel 之外另送一張 micro bubble，按下「換一批」會從
  session cache 取出下一組三家；移除單卡的「換一個」按鈕。
- **重設位置入口**：新增 `action=reset_location` postback（可綁定 Rich Menu）
  與 reset 提示卡片（含 `line://nv/location` 按鈕）；同時 `重設` / `reset` 文字
  指令也改走相同流程。重設時不再清空既有資料，只更新位置並回覆「已更新你的位置
  為『{新地名}』！」。

### 變更

- **移除第二地點**：users 表移除 `location_2_lat` / `location_2_lng`
  / `location_2_name`（內含 schema 改動與 `ALTER TABLE DROP COLUMN` 一次性
  migration）；推薦不再有平日／週末位置切換邏輯，`pick_anchor_location()` 簽章
  從 `(user, weekday)` 簡化為 `(user)`。
- **簡化 Onboard 流程**：移除「再設一個」步驟、`ask_second_location_card` 與
  `onboard_summary_card`；welcome 卡的「設定我的位置」按鈕改用 `line://nv/location`。
- **連續換一批 > 2 次才送引導訊息**：因為每次展示三家，2 批等於已看過 9 家，
  門檻由先前的 5 次調整為 2 次（per session 仍只發一次引導訊息）。

### 技術細節

- `database.py`：users 表 schema 縮減 + `LEGACY_USER_COLUMNS` migration；
  `init_db()` 啟動時嘗試 drop 舊欄位。
- `models.py`：`User` dataclass 移除 location_2 欄位。
- `services/onboard.py`：簡化 `set_location` 為單欄位、移除 `next_empty_slot`、
  新增 `mark_pending_reset()` / `consume_pending_reset()`（in-memory 集合）。
- `services/restaurant.py`：新增 `meal_type_for_hour()` 與 `MEAL_TYPE_WEIGHTS["supper"]`
  （沿用 dinner 權重）；移除已死掉的 `increment_swap()`。
- `services/session.py`：`swap_count` → `batch_count`、`next_restaurant` → `next_batch(size=3)`、
  `GUIDANCE_SWAP_THRESHOLD = 5` → `GUIDANCE_BATCH_THRESHOLD = 2`；新增
  `get_active_session(line_user_id)` 用於「換一批」postback 查找 session。
- `services/push.py`：`push_recommendation` 改推 carousel + 換一批控制卡片，支援
  `prefix_messages` 讓 onboard 把確認訊息一起送出；新增 `push_swap_batch` 取代
  舊的 `push_swap`。
- `flex_messages/daily_push.py`：改名為 `build_daily_bubble`，新增
  `build_daily_carousel` 與 `build_swap_batch_bubble`；移除單卡的「換一個」按鈕。
- `flex_messages/onboard.py`：移除 `ask_second_location_card` / `onboard_summary_card`、
  新增 `reset_location_card`。
- `routers/webhook.py`：onboard 流程改為一次設定位置即完成並推 carousel；新增
  `swap_batch` / `reset_location` postback handler；location handler 依序處理
  pending reset → 首次 onboard → adhoc。

## [Unreleased] - 2026-05-23

根據用戶回饋進行的推薦體驗優化，核心架構（FastAPI + APScheduler + SQLite）、
Onboard 流程、推播時段（06:30 / 11:30 / 17:30）與每週快報排程（週一 08:00）皆維持不變。

### 新增

- **店家黑名單（user_blacklist）**：新增 `user_blacklist` 表，可針對「特定店家」
  封鎖，與既有的 `user_exclusions`（封鎖餐廳「類型」）並行生效。日常推播卡片
  footer 在「帶我去 / 換一個」下方新增弱化的「不要再推這家」小字（xs、#AAAAAA、
  置中），透過 postback 寫入黑名單並回覆「好的，以後不會再推薦 {店名} 了。」，
  不會自動推下一家。
- **動態半徑擴展**：當篩選後（含黑名單、dedup、評分門檻、時段排除）候選少於 5 家
  時，自動將搜索半徑從預設 1500m 擴展至 3000m 重新查詢；使用擴展半徑時，會在
  時段標籤後附加「· 稍微遠一點，但值得走一趟」提示。
- **社交證明**：當餐廳在過去 7 天內有 2 位以上不同用戶點擊「帶我去」時，在卡片
  body 的距離／價位下方顯示「本週 N 人從這裡導航前往」（xs、#0F6E56）；無數據時
  不顯示任何 placeholder。
- **快報趣味數據**：每週飲食快報新增「本週被最多人封殺的餐廳」。

### 變更

- **放寬評分門檻**：所有餐廳篩選的最低評分從 `>= 4.0` 統一調整為 `>= 3.5`
  （日常推播、swap、adhoc、擴展半徑後的重新篩選皆套用）。評分仍作為加權因子，
  高分店被抽中的機率依然較高。
- **Swap 改為 session-based 排除 + cache**：每次推播觸發時一次性查詢約 20 家餐廳，
  篩選並加權排序後存入記憶體中的 session cache（key：`{user}:{date}:{meal_type}`）。
  之後每次「換一個」依序取出下一家，**不再隨機、不再循環回到看過的店**。
  - 清單耗盡時，以 3000m 擴展半徑重新查詢並排除所有已展示的 place_id。
  - 擴展後仍無新結果時，回覆「今天附近的選項都看過了 😅 傳一個新位置給我，
    或是等下一餐讓我重新幫你找！」。
  - 同一 session 連續 swap 超過 5 次時，額外發送一則引導訊息（每個 session 僅一次）：
    「附近的選項似乎都不太合胃口？傳一個位置給我，我幫你找更遠的好店 🗺️」。
  - Session 為 in-memory，服務重啟後清除（POC 可接受），重啟後 swap 會自動以
    擴展半徑重建 session。

### 技術細節

- `config.py`：新增 `EXPANDED_RADIUS_M = 3000`、`MIN_POOL_SIZE = 5`，
  `MIN_RATING` 由 `4.0` 改為 `3.5`。
- `database.py`：新增 `user_blacklist` 表，主鍵為 `(line_user_id, place_id)`。
- `services/session.py`（新檔）：swap session cache 與 push_log → session 對應。
- `services/restaurant.py`：新增 `build_candidate_pool`（取代 `pick_restaurant`，
  含動態半徑擴展與加權排序）、`add_blacklist`、`navigation_count_7d`。
- `services/push.py`：推播與 swap 改走 session 流程。
- `flex_messages/daily_push.py`：黑名單按鈕、社交證明、擴展半徑提示。

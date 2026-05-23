# 更新日誌

本專案的所有重大變更都會記錄在這個檔案。

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

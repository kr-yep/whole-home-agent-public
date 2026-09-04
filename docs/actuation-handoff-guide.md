# 智慧家電控制端對接與協作指南 (Actuation Handoff Guide)

本文件專為團隊組員撰寫，說明如何基於目前的 `ActuatorPort` 協議進行家電控制功能的延伸與硬體對接，確保每位組員在各自的工作進行到一半時，**拉取最新代碼不受任何衝擊（100% 向後相容）**。

---

## 1. 架構概述（六角架構與零硬體依賴）

為了讓軟體推理與實體家電解耦，專案採用標準的 Ports & Adapters 架構：

```text
[使用者自然語言] "幫我開客廳冷氣" / "把冷氣調到 26 度" / "關燈"
       │
       ▼
【意圖分流器 (CommandDispatcher)】
   ├─ 位置查詢句 ("鑰匙在哪裡？") ──> 走既有記憶回放推理 (完全不受影響)
   └─ 家電控制句 ("開冷氣")       ──> 走動作執行管道
       │
       ▼
【安全防護閘 (ActionPolicy)】
   * 白名單檢驗 (限制操作已登記設備)
   * 邊界防護 (例如冷氣僅允許 18°C ~ 30°C，防止模型暴走)
       │
       ▼
【執行端介面 (ActuatorPort)】 ── (所有組員擴充的標準進入點)
       ├─────────────────────────┐
       ▼                         ▼
【MockActuator (預設啟用)】     【HomeAssistantActuator (真機)】
  * 記憶體模擬，零硬體門檻           * 透過 REST API 呼叫 Home Assistant
  * 組員本地測試一秒跑通             * 實際聯動實體冷氣、SwitchBot、窗簾
       │
       ▼
【執行收據 (ActionReceipt)】
  * 生成不可變、帶有時間戳與執行狀態的收據
  * Streamlit 介面即時動態更新設備狀態面板
```

---

## 2. 協議規格（核心介面）

所有家電執行器皆實作位於 `src/whole_home_agent/actuation/port.py` 的標準協議：

```python
from whole_home_agent.actuation.models import ActionRequest, ActionReceipt, DeviceState

class ActuatorPort(Protocol):
    def execute(self, request: ActionRequest) -> ActionReceipt:
        """執行或模擬動作，並返回操作收據。"""
        ...

    def get_device_state(self, device_id: str) -> DeviceState | None:
        """獲取指定設備的當前狀態。"""
        ...

    def list_devices(self) -> list[DeviceState]:
        """列出所有受控設備清單。"""
        ...
```

### 支援的預設設備：
* `living_room_ac`：客廳冷氣（支援開關、調整溫度）
* `living_room_light`：客廳大燈（支援開關）
* `bedroom_light`：臥室電燈（支援開關）
* `living_room_curtain`：客廳窗簾（支援開關、開合百分比 0%~100%）

---

## 3. 組員如何進行對接與協作？

### A. 若您負責「硬體對接 / IoT 設備聯動」
您不需要修改核心邏輯或 Streamlit UI，只需專注於實體適配器：

1. **對接 Home Assistant**：
   在環境變數中設定您的 HASS 伺服器資訊：
   ```powershell
   $env:HASS_URL = "http://your-homeassistant-ip:8123"
   $env:HASS_TOKEN = "your_long_lived_access_token"
   ```
   `HomeAssistantActuator` 會自動透過 REST API 呼叫對應的 `climate.set_temperature`、`light.turn_on` 或 `cover.set_cover_position`。

2. **新增其他廠牌（如 SwitchBot 官方 API、Matter、米家）**：
   只需在 `src/whole_home_agent/adapters/` 新增一個 class 並實作 `ActuatorPort` 即可，例如：
   ```python
   class SwitchBotBluetoothActuator(ActuatorPort):
       def execute(self, request: ActionRequest) -> ActionReceipt:
           # 您的 BLE 連線與指令發送邏輯
           ...
   ```

### B. 若您負責「NLP / 大語言模型語意擴充」
目前內建確定性解析器 `parse_action_command`，若您希望支援更口語、模糊的問句（例如「我覺得房間好悶」、「外面好亮」）：
* 可以在 `src/whole_home_agent/actuation/parser.py` 或 `dispatcher.py` 中引入 LLM 意圖映射，將口語轉換成標準的 `ActionRequest(target_device_id="...", action_type=...)`。

### C. 若您負責「前端介面 / Streamlit UI 優化」
* 所有介面邏輯位於 `src/whole_home_agent/memory_app.py` 中的 `_render_devices_panel` 與 `_render_action_receipt`。
* 您可以自由添加開關切換器（Toggle switch）、滑桿（Slider 控制窗簾或溫度），呼叫 `actuator.execute()` 即可。

---

## 4. 常用驗證指令

在專案目錄下，組員可以隨時透過以下指令確保所有功能正常：

```powershell
# 執行全套單元測試（包含既有 518 測試 + 新增 14 項家電測試）
.\.demo-venv\Scripts\python.exe -m unittest discover -s tests -v

# 啟動 Streamlit 介面（包含智慧家電面板與自然語言問答）
.\.demo-venv\Scripts\streamlit.exe run src/whole_home_agent/memory_app.py

# 發布審計檢查（確保無未授權的敏感資料或破壞性違規）
.\.demo-venv\Scripts\python.exe tools/audit_public_release.py
```

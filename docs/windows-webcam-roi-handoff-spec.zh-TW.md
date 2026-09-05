# Whole Home Agent Windows 網路攝影機輸入至 ROI 傳遞整合規格書

- 文件編號：`WHA-WIN-CAPTURE-ROI-001`
- 版本：`1.2-draft`
- 建立日期：`2026-09-04`
- 修訂日期：`2026-09-05`
- 文件狀態：`PROPOSED / R1 CORE IMPLEMENTED`
- 執行狀態：`OPERATE DISABLED`
- 目標環境：Windows 11 x64、USB/UVC 彩色網路攝影機 1 台
- 目標範圍：從網路攝影機擷取影像，至 ROI 處理入口確認受理為止

---

## 1. 本文件的定位

本文件旨在為 Whole Home Agent 未來導入網路攝影機（Webcam）預作準備，將在 Windows 上擷取視訊、並將正規化後的完整影格（Full frame）安全且可驗證地傳遞至 ROI 處理入口的各項規範整合為單一文件。其目的在於僅憑本文件即可確認負責範圍、系統邊界、資料格式、處理順序、異常處理機制、開發隔離、測試方法及完成條件。

本文件為整合 ADR 0025、ADR 0026、ADR 0027 及詳細通訊協定草案之實作規格提案，並非已正式採納之營運方針。編寫本文件、完成程式實作或測試通過，均不代表已被允許使用攝影機、擷取家庭內部資料、拍攝人像、儲存、對外傳送或操作裝置。目前程式庫中仍持續維持 `OPERATE DISABLED` 狀態。

本文件中註明為「必須」之事項，代表未來實作此規格提案時的合規條件。在 `ACTION_POLICY.md`、`PROJECT_STATE.md`、相關人員同意、角色劃分、裝置與攝影機註冊，以及執行許可尚未確立之前，僅以使用生成影像的離線測試為適用對象。

- **1.1-draft** 維持 1.0-draft 的 ROI 入口邊界與 wire v1 規格，並釐清在 R0 review 中指出的設定 profile、source-end 缺失、cleanup code、攝影機生命週期，以及同步逾時之佐證限制（evidence limit）。此外，不同 AppContainer 間的具名管道（named pipe）在通過 R2A 可行性驗證前，均視為未定案。
- **1.2-draft** 則反映了 Windows 的 SharedReadOnly 無法變更影格來源格式（frame source format）的限制，將未來的 live profile 修改為 ExclusiveControl。獨占控制（exclusive control）的用途，嚴格限定於透過 `SetFormatAsync` 進行單次設定，套用註冊時所固定的 1280×720 exact MediaFrameFormat。嚴禁進行對焦、曝光、變焦等攝影機控制，亦禁止 fallback 至其他格式/裝置或由 reader 進行縮放（resize）。wire v1、ROI 入口、raw retention、R2A/R4 gate 則維持不變。

---

## 2. 目的

本次負責作業的目標在於：有別於目前直接讀取固定影片的展示環境，定義未來接收 Windows 網路攝影機輸入的邊界，並確保下列流程具有可重現性：

```text
從網路攝影機取得 1 個影格
  -> 正規化為指定尺寸與色彩格式
  -> 轉換為明確標註順序、時間、遺漏的訊息
  -> 透過隔離的本機通訊傳送至 SemanticHost
  -> 進行嚴格驗證
  -> 以唯讀方式傳遞至 ROI 處理入口
  -> 確認 ROI 端已受理並釋放緩衝區
```

此項作業的成果為「影像已正確送達 ROI 入口」的傳輸結果。辨識出物體、選取正確的 ROI、追蹤鑰匙或包包、理解家庭內部事實等，均不在本次成果範圍內。

---

## 3. 負責範圍

### 3.1 包含項目

本作業包含下列內容：
- 使用生成影格進行契約測試之輸入
- 未來獲得許可時的網路攝影機初始化、啟動、停止與銷毀
- 彩色影格擷取
- 以 10 Hz 固定週期為擷取位置（acquisition position）編號
- 正規化為 1280×720、RGB24
- 統一方向、鏡像、行間距（row stride）、座標系
- 表達影格、遺漏、開始、結束的有限工作階段協定（finite session protocol）
- 最多 3 個影格的傳送佇列
- 透過 Windows 具名管道進行單向本機傳輸
- 驗證管道連線對象、訊息格式、長度、順序、時間、雜湊值
- 同步向 ROI 入口借出（lease）唯讀影格
- 確認 ROI 的受理、拒絕、逾時及緩衝區釋放
- 在工作階段結束時產生傳輸收據（delivery receipt）
- 發生失敗時的 fail-closed 處理
- 確實釋放攝影機、管道與緩衝區
- 不包含影像資料的結構化記錄（structured log）與彙總指標

### 3.2 不包含項目

本作業不包含下列內容：
- 選擇 ROI 矩形或多邊形
- 影格的裁切（crop）、拼貼（tile）、縮放（resize）、留黑邊（letterbox）
- 透過動態偵測進行影格篩選
- 物體偵測、追蹤、嵌入（embedding）、關聯推論
- 產生 ClaimCandidate、claim commit、帳本（ledger）、投影（projection）
- 問答、Streamlit 顯示、LLM/VLM、展示端（presenter）
- SQLite 或其他持久化儲存
- 儲存原始影格、影片、縮圖、裁切後影像
- 雲端 API、localhost HTTP、TCP、WebSocket、RTSP
- 音訊、麥克風、人臉辨識、人物識別
- 多攝影機支援、攝影機間 ID 繼承、自動重新連線
- 連續監控、無人值守執行、24 小時運作
- 於真實家庭、人物、私人空間中使用
- 裝置操作或物理動作

---

## 4. ROI 的定義與責任邊界

本文件中的 ROI 代表「感興趣區域」（Region of Interest）的處理階段。但本次負責的傳輸邊界並非計算 ROI 後的結果，而是 ROI 處理階段接收正規化完整影格的「入口」。

因此，負責範圍的終點定義為滿足下列條件之時間點：
1. SemanticHost 已驗證單一影格的結構、尺寸、順序與時間。
2. ROI 入口已收到同一個影格的唯讀租約（read-only lease）。
3. ROI 入口已完成必要的同步處理。
4. ROI 入口僅釋放了 1 次 lease。
5. ROI 入口回傳了同一工作階段、同一序號的 `ACCEPTED`。

若 ROI 端後續需產生矩形、多邊形或裁切影像，均屬於另一份契約。本次的 CaptureHost 或 CaptureStreamDecoder 嚴禁預先決定 ROI，亦不得解讀後續階段的偵測結果。

若相關人員將「傳送至 ROI」解讀為「產生 ROI 裁切影像並傳給下一階段」，由於與本文件所定義的邊界不同，應於實作前暫停並另行制定其他版本的規格。

---

## 5. 系統架構

未來的 Windows 架構將具備攝影機權限的 CaptureHost，與具備 ROI 及語意處理能力的 SemanticHost 拆分為不同的程序，並以各自獨立的 AppContainer ID 進行隔離。

```text
使用者點擊畫面上的 Start
       |
       v
+------------------------------------------------------+
| Wha.CaptureHost                                      |
| C# / WinUI 3 / MSIX AppContainer                     |
| 權限：僅限 webcam                                    |
| MediaCapture + MediaFrameReader                      |
| 編號 -> RGB24 轉換 -> 3-slot 佇列 -> pipe 傳送       |
+----------------------------+-------------------------+
                             |
                             | Windows named pipe
                             | 單向、單一連線、長度限制、DACL 限制
                             v
+------------------------------------------------------+
| Wha.SemanticHost                                     |
| 獨立的 MSIX AppContainer / 固定 Python runtime       |
| 無 webcam、microphone、網路、廣域檔案系統權限        |
| decoder -> validator -> ROI ingress                  |
+----------------------------+-------------------------+
                             |
                             | RoiAcceptResultV1
                             v
                       本次負責作業完成
```

CaptureHost 僅為攝影機配接器（adapter），並非模型、資料庫、狀態管理、問答系統或外部服務。SemanticHost 則不具備攝影機 API 及權限，僅將接收到的暫存影格轉交至 ROI 入口。

在一般的 Python 環境、目前的 CLI、現行的 Streamlit、macOS/Linux 測試環境及現有展示程式中，嚴禁建置、安裝、啟動、引用（import）CaptureHost 或列舉攝影機。

---

## 6. 執行 Profile

嚴格區分以下 3 種 profile：

| Profile | 輸入來源 | 目的 | 目前處理方式 |
|---|---|---|---|
| `stream_sim_d0` | Python 生成 RGB | 單純契約測試 | 未來可實作 |
| `windows_generated_ipc_v1` | Windows 套件內生成 RGB | AppContainer 間通訊測試 | 待另行提出實作需求後方可進行 |
| `windows_webcam_d1_v1` | 已註冊的網路攝影機 | 實體機驗收測試 | 目前嚴格禁止 |

所有 profile 均使用相同的訊息結構與 ROI 契約。嚴禁為生成測試專門製作簡化格式或不同的 ROI 介面。

除非執行許可、角色、同意書、攝影機功能（capability）、視野、執行期限、已簽署套件 hash 與設定 hash 完全相符，否則嚴禁選取 `windows_webcam_d1_v1`。絕對不可僅透過環境變數、提示詞（prompt）、LLM 輸出、import、副作用（side effect）或一般 CLI 選項將其啟用。

---

## 7. 固定參數

初始 v1 的固定參數定義如下：

| 項目 | 數值 |
|---|---|
| Capture schema | `whole-home-agent.capture-message.v1` |
| ROI session schema | `whole-home-agent.roi-ingress-session.v1` |
| ROI frame schema | `whole-home-agent.roi-ingress-frame.v1` |
| ROI gap schema | `whole-home-agent.roi-ingress-gap.v1` |
| ROI end schema | `whole-home-agent.roi-ingress-end.v1` |
| ROI result schema | `whole-home-agent.roi-accept-result.v1` |
| ROI receipt schema | `whole-home-agent.roi-delivery-receipt.v1` |
| ROI profile | `windows_webcam_roi_v1` |
| 影像寬度 | 1280 pixel |
| 影像高度 | 720 pixel |
| pixel format | `rgb24` |
| 通道順序 | R、G、B |
| 通道深度 | unsigned 8 bit |
| 陣列 layout | contiguous height x width x 3 |
| row stride | 3840 byte |
| 單一影格 payload | 2,764,800 byte |
| 原點 | 左上角 |
| x 軸 | 向右 |
| y 軸 | 向下 |
| 旋轉 | 正規化為 0 度 |
| 鏡像 | 無 |
| ROI 端色彩解讀 | sRGB |
| 擷取週期 | 10/1 position per second |
| 單一 position 間隔 | 100,000,000 ns |
| 標準擷取時間 | 30,000,000,000 ns |
| 標準 position 數 | 300 |
| CaptureHost frame slot | 3 |
| decoder frame slot | 1 |
| ROI lease slot | 1 |
| 應用程式影格上限 | 總計 5 |
| 標準 temporal gap 上限 | 2 position |
| metadata 上限 | 8,192 byte |
| body 上限 | 2,764,800 byte |
| raw retention | `none` |
| audio | `false` |
| network egress | `false` |
| camera sharing | `exclusive_control`，僅限 format 設定 |
| camera control scope | `format_only` |
| source format fallback | `false` |
| reader resize | `false` |

若需修改解析度、色彩格式、週期、佇列或保留機制，必須同步更新設定 hash 與測試結果。若變更涉及 wire 相容性，嚴禁直接覆寫 v1，必須另行提出 v2 提案。

---

## 8. 設定與 Hash

在各個執行 profile 中，CaptureHost、decoder 與 ROI 均必須使用該 profile 所對應的同一組已解析設定。R1 使用 `configs/capture/stream-sim-d0-v1.toml`，並明確將 `profile_id=stream_sim_d0` 對應至 wire 上的 `source_profile=generated_stream_d0`。以下範例僅供未來的 live profile 使用，不可重複作為 R1/R2 的 hash。設定檔必須在建立管道或開啟攝影機之前讀取完畢（僅讀取一次），並拒絕任何未知 key、缺失 key、重複 key、錯誤型別或超出範圍之數值。本機上限絕對不可因訊息傳送端傳入的數值而擴增。

初始設定至少應包含下列內容：

```toml
schema = "whole-home-agent.capture-config.v1"
profile_id = "windows_webcam_d1_v1"
width = 1280
height = 720
pixel_format = "rgb24"
target_fps_numerator = 10
target_fps_denominator = 1
sampling_interval_ns = 100000000
max_positions = 300
sampling_window_ns = 30000000000
camera_initialization_timeout_ns = 5000000000
camera_open_to_close_limit_ns = 37000000000
pipe_connect_timeout_ns = 5000000000
pipe_inactivity_timeout_ns = 1000000000
roi_accept_timeout_ns = 100000000
end_flush_timeout_ns = 2000000000
resource_release_timeout_ns = 2000000000
queue_capacity = 3
roi_capacity = 1
max_gap_frames = 2
raw_retention = "none"
audio_enabled = false
network_egress_enabled = false
camera_sharing_mode = "exclusive_control"
camera_control_scope = "format_only"
allow_source_format_fallback = false
allow_reader_resize = false

[transport]
wire_version = 1
max_metadata_bytes = 8192
max_body_bytes = 2764800
pipe_instances = 1

[roi]
profile_id = "windows_webcam_roi_v1"
layout = "HWC_CONTIGUOUS"
row_stride_bytes = 3840
origin = "top_left"
x_axis = "right"
y_axis = "down"
rotation_degrees = 0
mirrored = false
color_interpretation = "srgb"
```

在 live profile 中，裝置註冊流程所產生的下列 `[camera_source]` 物件亦為必要項目：

| 欄位 | 條件 |
|---|---|
| `binding_schema` | `whole-home-agent.camera-format-binding.v1` |
| `frame_source_ref` | 不含硬體 ID 的不透明（opaque）註冊參照 |
| `stream_kind` | `color` |
| `width`, `height` | 1280, 720 |
| `source_subtype` | 註冊時確切且經過大小寫正規化（case-normalized）的 subtype |
| `frame_rate_numerator`, `frame_rate_denominator` | 註冊時確切的正分數，必須在 10 fps 以上 |
| `reader_output_subtype` | `BGRA8` |
| `format_fingerprint` | 上述 binding 欄位的標準形式（canonical）SHA-256 |

此物件並非執行時期的推測值，而是由人工審核註冊流程所產生的輸出。將其合併至 base config 後的整體內容將作為計算 `capture_config_hash` 的對象；若遺漏此物件，live config 將視為未解析，嚴禁開啟攝影機。

設定 hash 的計算方式為：套用預設值後，將所有純量值（scalar value）依 key 排序轉換為標準形式的 canonical JSON，再對其 UTF-8 位元組陣列進行 SHA-256 運算，產生 64 個小寫十六進位字元。`capture_config_hash` 涵蓋整體 Capture 設定，而 `roi_config_hash` 則以 ROI 設定及 ROI schema 版本為對象。

設定 hash 僅為設定內容位元組的識別碼（identity），不能作為攝影機、影像、同意書、真實性或現實世界狀態的證明。

---

## 9. 識別碼

`capture_session_id` 為代表單次 producer 生命週期（lifetime）的不透明 ID。未來的實體機執行環境必須使用標準小寫 UUIDv4，若遇重新連線、重新啟動或重試，均必須核發全新的 ID。在生成測試中，則可使用固定於 manifest 中的測試用 ID。

`source_id` 為以 profile 為單位的 opaque ID，不得包含人名、房間名稱、地址、帳號、攝影機產品名稱或使用者輸入之字句。ID 長度應介於 1 至 128 個字元的可列印 ASCII（printable ASCII），且不可包含控制字元與空白。

攝影機硬體 ID 僅能保存在信任啟動邊界（trusted launch boundary）內部，嚴禁傳遞至 wire、ROI value、收據或記錄中。

---

## 10. Windows 攝影機擷取規格

本章節僅在未來 R4 獲得個別許可時適用。

CaptureHost 必須使用 `MediaCapture` 與彩色的 `MediaFrameReader`。嚴禁使用 Python 的 `VideoCapture(0)`、攝影機索引值（index）、OpenCV 列舉或 DirectShow fallback 機制。

攝影機啟動順序如下：
1. SemanticHost 建立具名管道伺服端。
2. CaptureHost 與 SemanticHost 互相驗證彼此的套件/AppContainer 身分識別（identity）。
3. 使用者在 CaptureHost 畫面上點擊 Start。
4. 信任邊界重新確認執行許可、有效期限、套件 hash、裝置功能（capability）及設定 hash。
5. CaptureHost 僅開啟已註冊的單一設備，並設定為僅限視訊（video-only）、CPU 記憶體及 `ExclusiveControl` 模式。
6. 僅挑選 1 筆與註冊時固定的 source ID、stream kind、1280×720、subtype、影格率分數、format fingerprint 完全相符的 `MediaFrameFormat`，並呼叫 1 次 `SetFormatAsync`。若符合項目為 0 筆或有多筆，則視為失敗。
7. 再次確認 CurrentFormat 與註冊值完全吻合。
8. 建立固定 `BGRA8` 輸出 subtype 且不指定 BitmapSize 的 reader，並禁止 resize。
9. 啟動 reader。
10. 傳送 start 訊息，開始進行為期 30 秒的 position 生成。
11. 處理完 300 個 position 或使用者點擊 Finish 後，停止並銷毀 reader 與攝影機。
12. 僅在確認攝影機成功釋放後，才發送 SEALED end。
13. SemanticHost 執行驗證、關閉 ROI、產生收據並釋放管道。

管道連線與雙向身分驗證必須在開啟攝影機前的 5 秒內完成。攝影機與 reader 初始化時限為 5 秒，從開啟攝影機到關閉的時間上限為 37 秒。畫面上的擷取指示器（capture indicator）必須從開啟攝影機前持續顯示至攝影機銷毀之後。

若無註冊攝影機、裝置 ID 變更、權限遭拒、無法提供 1280×720、exact format 未能唯一吻合、無法取得 exclusive control，或驅動程式自動 fallback 至其他格式，均不得啟動。絕對不可自動切換至 shared 模式、其他攝影機、其他解析度或讓 reader 進行縮放。

`ExclusiveControl` 僅能用於格式設定。CaptureHost 嚴禁存取或呼叫 VideoDeviceController、對焦（focus）、曝光（exposure）、變焦（zoom）、白平衡（white balance）、手電筒/補光燈（torch）、水平/垂直旋轉（pan/tilt）或廠商自訂屬性（vendor property）。包含 source subtype 與影格率分數在內的 exact format，必須在人工審查的裝置註冊階段固定，並將正規化後的數值 hash 納入 live 設定中。現階段由於尚未註冊攝影機，切勿捏造格式數值或 live 設定 hash。

由於 `SharedReadOnly` 無法變更影格來源格式，且僅在驅動程式目前的數值碰巧符合時才能保證格式完全相符，因此本 profile 不予採用。

---

## 11. 影像正規化規格

CaptureHost 必須將選定的 source frame 進行單次轉換為下列 canonical frame：
- **shape**: 720 x 1280 x 3
- **layout**: `HWC_CONTIGUOUS`
- **channel order**: `RGB`
- **dtype**: `uint8`
- **stride**: 3840 bytes
- **origin**: top-left
- **x direction**: right
- **y direction**: down
- **rotation**: 0 degrees
- **mirrored**: false
- **payload bytes**: 2,764,800

若驅動程式輸入為 BGRA8，則將 B、G、R 的順序重新排列為 R、G、B，並捨棄 alpha 通道。若允許使用 NV12 等其他 source subtype，必須事先固定 Windows 上的轉換路徑，並透過生成的色彩檢驗圖（color bar）進行測試。擷取端不得進行裁切、縮放、留黑邊、拼貼、銳化、降噪、動態濾波或物件判定。

ROI 之後的 bounding box 座標必須基於原始影格的 xyxy 格式，採用包含 x1, y1 但不包含 x2, y2 的左閉右開（max-exclusive）表示法。允許範圍為 `0 <= x1 < x2 <= 1280`、`0 <= y1 < y2 <= 720`。本次擷取處理雖然不產生 box，但必須固定座標系統，以便後續處理階段能反推回原始影像。

---

## 12. 擷取時間與 Position 編號

Windows 的兩個程序均直接使用 QueryPerformanceCounter（QPC）。將計數值 c 與頻率 f 轉換為奈秒（nanosecond）時，不使用浮點數，而是依下列公式計算：

$$q = c \mathbin{//} f$$
$$r = c \bmod f$$
$$\text{monotonic\_ns} = q \times 1{,}000{,}000{,}000 + (r \times 1{,}000{,}000{,}000) \mathbin{//} f$$

運算必須包含溢位檢查（overflow check）。此時間為本機單調時間（monotonic time），並非 UTC、攝影機曝光時間或拍攝時間戳記。`captured_monotonic_ns` 定義為 CaptureHost 首度將選定的 source frame 納入應用程式所有權（ownership）後立即量測到的 QPC 時間。

令 `start.started_monotonic_ns = t0`，position $n$ 的截止時間（deadline）定義如下：

$$\text{deadline}(n) = t_0 + (n + 1) \times 100{,}000{,}000\text{ ns}\quad (0 \le n < 300)$$

在每個截止時間點，必須記錄 1 個 position（以 frame 或 gap 形式記錄）。嚴禁將同一個 source frame 套用至多個 position。嚴禁將未來的 frame 分配給過去的 position。嚴禁透過重複使用舊 frame 來隱瞞遺漏（gap）。

在各 position 中，必須使用較上次使用的 frame 更具時效性、且在當前截止時間之前所觀測到的最新 frame。若無可用 frame，原因記為 `source_unavailable`；若轉換處理無法及時完成，記為 `capture_overrun`；若已轉換的 frame 無法排入傳送佇列，則記為 `queue_overflow`。

僅有相同原因的連續 gap 才能合併為單一區間記錄。待發送的 gap 必須先於後續的 frame 發送。若無法發送 gap，則不得進行 seal，應直接判定失敗。

---

## 13. CaptureMessageV1 Wire 規格

具名管道上的每筆記錄（record）由 16 位元組固定前綴（prefix）、標準 JSON（canonical JSON）metadata，以及僅在必要時附帶的 raw frame body 依序組成。

### 13.1 固定 Prefix

| offset | size | 型別 | 數值 |
|---|---|---|---|
| 0 | 4 | byte | ASCII `WHA1`，hex `57 48 41 31` |
| 4 | 1 | u8 | wire major version 1 |
| 5 | 1 | u8 | 1=start, 2=frame, 3=gap, 4=end |
| 6 | 2 | u16be | flags，必須為 0 |
| 8 | 4 | u32be | metadata length |
| 12 | 4 | u32be | body length |

metadata 長度必須介於 2 至 8,192 位元組之間。body 僅在訊息型態為 frame 時必須為 2,764,800 位元組，其餘型態必須為 0 位元組。decoder 必須完整讀取 prefix，並在驗證 version、kind、flags、length 無誤後，方可分配緩衝區空間。由於管道讀取可能發生分段（fragmented），因此不可預設單次讀取操作就能取得完整的 record。

嚴禁使用壓縮、分塊傳輸（chunking）、額外結尾（trailer）、其他像素 body、未知 flag 或版本降級（version downgrade）。

### 13.2 Canonical JSON

metadata 必須為 UTF-8 編碼的頂層 JSON 物件，key 必須依照 Unicode code point 排序，不得包含多餘的空白字元，布林值與 null 必須以小寫表示。整數必須為十進位，且不得包含無意義的前導零、+ 號、小數點、指數記號、NaN 或 Infinity。必須嚴格拒絕 BOM、註解、重複 key、未知 key、遺漏 key、陣列型態或未知的巢狀物件。

decoder 解析後必須按照相同規則重新編碼（re-encode），若與原始位元組不完全一致則必須予以拒絕。若 Python 與 C# 的輸出結果不一致，以程式庫內固定的跨語言一致性測試向量（cross-language conformance vector）為準。

### 13.3 通用欄位

所有訊息均必須具備下列欄位：

| 欄位 | 條件 |
|---|---|
| `schema` | `whole-home-agent.capture-message.v1` |
| `kind` | 必須為 `start`, `frame`, `gap`, `end` 其中之一 |
| `capture_session_id` | 工作階段期間不可變更 |
| `source_id` | 工作階段期間不可變更 |

prefix 中的 kind 與 metadata 中的 kind 必須一致。

### 13.4 Start

start 訊息僅能在最初發送 1 次，其 body 必須為 0 位元組。附加欄位定義如下：

| 欄位 | 條件 |
|---|---|
| `source_profile` | 目前僅限 `generated_stream_d0`。未來獲得許可後將擴充 `windows_webcam_d1_v1` |
| `capture_config_hash` | 小寫 SHA-256，長度 64 字元 |
| `width`, `height` | 1280, 720 |
| `pixel_format` | `rgb24` |
| `target_fps_numerator`, `target_fps_denominator` | 10, 1 |
| `started_monotonic_ns` | unsigned 64-bit integer |
| `activation_decision_id` | 生成測試時為 null，獲許可的 live 運作時為 opaque reference |
| `policy_version` | 生成測試時為 null，獲許可的 live 運作時為採納的 policy reference |
| `raw_retention` | `none` |
| `audio_enabled` | `false` |
| `network_egress_enabled` | `false` |

activation ID 與 policy version 僅作為佐證參照，訊息本身並不能直接賦予權限。

### 13.5 Frame

frame metadata 的附加欄位如下。RGB 位元組不得以 base64 形式放入 metadata 中，必須置於 record body：

| 欄位 | 條件 |
|---|---|
| `source_sequence` | 必須與 decoder 預期的下一個 position 一致 |
| `captured_monotonic_ns` | 大於或等於 start 時間，且相較於前一筆訊息呈現非遞減（non-decreasing） |
| `width`, `height` | 1280, 720 |
| `pixel_format` | `rgb24` |

body 長度必須恰好為 2,764,800 位元組。嚴禁將 raw bytes 輸出至記錄、例外處理訊息、JSON、SQLite、檔案、presenter 或模型 context 中。

### 13.6 Gap

gap 用於明確宣告未能成功傳送的 position，其 body 必須為 0 位元組：

| 欄位 | 條件 |
|---|---|
| `first_missing_sequence` | decoder 預期的下一個 position |
| `last_missing_sequence` | 大於或等於 first，且小於或等於 299 |
| `detected_monotonic_ns` | 大於或等於 start 時間，且相較於前一筆訊息呈現非遞減 |
| `reason` | `capture_overrun`, `queue_overflow`, `source_unavailable` |

gap 之後的下一個 position 應為 `last_missing_sequence + 1`。長度達 3 個 position 以上的 gap，將要求 ROI 重設其時序狀態（temporal state reset）。

### 13.7 End

end 訊息僅能在最後發送 1 次，其 body 必須為 0 位元組：

| 欄位 | 條件 |
|---|---|
| `status` | `SEALED`, `ABORTED`, `FAILED` |
| `last_source_sequence` | 最後核算（accounted）的 position，若為空則為 null |
| `frame_count` | frame 訊息總數 |
| `dropped_frame_count` | gap position 總數 |
| `ended_monotonic_ns` | 大於或等於所有訊息的時間戳記 |
| `stream_sha256` | 僅在狀態為 SEALED 時提供小寫 64 字元字串，其餘為 null |
| `failure_code` | 狀態為 SEALED 時為 null，其餘為固定代碼 |

若非空值，必須滿足 `frame_count + dropped_frame_count = last_source_sequence + 1`；若為空值，則兩項計數皆為 0。在標準的 300 個 position 情況下，`last_source_sequence=299`。

capture failure code 僅允許下列項目：
- `CAPTURE_CANCELLED`
- `CAPTURE_PIPE_FAILED`
- `CAPTURE_DEVICE_LOST`
- `CAPTURE_FORMAT_CHANGED`
- `CAPTURE_TIMEOUT`
- `CAPTURE_RESOURCE_RELEASE_FAILED`
- `CAPTURE_INTERNAL_FAILED`

---

## 14. Stream Digest

CaptureHost 與 SemanticHost 各自獨立計算 stream SHA-256。其原像（preimage）順序定義如下：

```text
UTF-8("whole-home-agent.capture-stream.v1\0")
capture_config_hash 的原始 32 位元組
u64be(width) || u64be(height)
u64be(target_fps_numerator) || u64be(target_fps_denominator)
UTF-8("rgb24\0")
每個 frame:
  0x46 || u64be(source_sequence)
       || u64be(captured_monotonic_ns - started_monotonic_ns)
       || u64be(len(rgb_bytes)) || rgb_bytes
每個 gap:
  0x47 || u64be(first_missing_sequence) || u64be(last_missing_sequence)
       || u64be(detected_monotonic_ns - started_monotonic_ns)
       || reason_code
```

reason code 分別為：`capture_overrun=0x01`、`queue_overflow=0x02`、`source_unavailable=0x03`。`u64be` 代表 64 位元無號大端序（unsigned 64-bit big-endian）整數。

decoder 必須與 `end.stream_sha256` 進行常數時間比對（constant-time comparison）。若不相符，應將該工作階段標記為失敗，且不得將成功結果傳遞給 ROI 及後續階段。摘要值僅能證明接收到的位元組一致性，無法證明攝影機真實性、拍攝時刻、場景完整性或現實事實。亦不可在記錄或收據中保留單一影格的雜湊值。

---

## 15. 具名管道與連線身分驗證

邏輯管道名稱（logical pipe name）定義如下：

```text
\\.\pipe\LOCAL\wha.capture.v1.<session_nonce>
```

`session_nonce` 為各工作階段生成的 128 位元隨機小寫 32 碼十六進位字串。該數值僅用於路由目的，並非身分驗證、同意或授權權杖（token）。工作階段結束後不再保留。

管道必須設定為 byte mode、非同步、SemanticHost 端僅限接收（inbound-only）、CaptureHost 端僅限傳送（outbound-only）、伺服器執行個體上限 1、用戶端上限 1。SemanticHost 嚴禁使用預設安全性描述元（default security descriptor），必須針對 CaptureHost 與 SemanticHost 精確的 AppContainer SID 設定最小權限，並明確拒絕 Anonymous SID 與 Network SID。

SemanticHost 必須驗證連入的用戶端程序權杖（process token）與套件/AppContainer SID，CaptureHost 亦須驗證伺服端程序權杖與 SemanticHost 的套件身分。停用模擬（impersonation）功能。若無法確認身分，則嚴禁開啟攝影機並終止連線。

將 nonce 傳遞給 CaptureHost 的啟動機制，將在 R2 階段於 Windows 套件上驗證其可行性後予以固定。嚴禁使用檔案、登錄檔（registry）、環境變數、剪貼簿、TCP、使用者提問或模型輸出進行傳遞。

---

## 16. ROI Ingress 契約

呼叫順序遵循下列邏輯 API：

```python
roi.open_session(RoiIngressSessionV1) -> None
roi.accept(RoiIngressFrameV1, RoiFrameLeaseV1) -> RoiAcceptResultV1
roi.accept_gap(RoiIngressGapV1) -> None
roi.close_session(RoiIngressEndV1) -> None
roi.abort_session(RoiIngressEndV1 | None) -> None
```

呼叫必須採單執行緒（single-thread）、不可重入（non-reentrant），且嚴格遵循序號順序。僅有在正常 SEALED 狀態下呼叫 1 次 `close_session`；在 ABORTED、FAILED 或 decoder 發生異常時，則呼叫 1 次具等冪性（idempotent）的 `abort_session`。

### 16.1 RoiIngressSessionV1

session 物件包含 schema、capture/session ID、source profile、capture config hash、ROI profile、ROI config hash、ROI implementation version、width、height、pixel format、layout、stride、origin、axis、rotation、mirror、color interpretation、target FPS、start QPC、max positions、max gap 以及 raw retention。

layout 等參數必須根據納入 hash 範圍的本機設定產生，不得採納 frame 訊息中所指定的未定義數值。

### 16.2 RoiIngressFrameV1

frame descriptor 具備下列欄位：

| 欄位 | 條件 |
|---|---|
| `schema` | `whole-home-agent.roi-ingress-frame.v1` |
| `capture_session_id` | 必須與 open session 一致 |
| `source_sequence` | 經過驗證的 position |
| `source_offset_ns` | 擷取時間減去 session start 時間之差值 |
| `captured_monotonic_ns` | 經過驗證的 QPC 時間 |
| `width`, `height`, `pixel_format` | 必須與 session 一致 |
| `layout`, `row_stride_bytes` | `HWC_CONTIGUOUS`, 3840 |
| `origin`, `rotation_degrees`, `mirrored` | `top_left`, 0, `false` |
| `payload_length` | 2764800 |

像素位元組不得包含於 descriptor 中，僅能透過 `RoiFrameLeaseV1` 傳遞。嚴禁在 repr、JSON、例外狀況或記錄中輸出像素內容。

### 16.3 RoiFrameLeaseV1

lease 提供 2,764,800 位元組的連續唯讀檢視（contiguous read-only view）與單次使用的 `release()` 方法。
- 同一時間僅能存在 1 個有效 lease。
- ROI 在從 accept 返回之前，必須呼叫且僅能呼叫 1 次 `release()`。
- ROI 不得保留完整影格的檢視（full-frame view）或別名（alias）。
- 嚴禁修改底層緩衝區（backing buffer）。
- 重複 release、未呼叫 release 或在 release 後存取，均判定為 `ROI_BUFFER_LEAK`。

回傳的 accept 必須在 SemanticHost QPC 時間 100,000,000 ns 內完成。R1 僅能在返回後判定是否逾時，不保證可強制中斷程序內的 Python 呼叫。在 R2 階段，必須先證明外部 SemanticHost watchdog 能針對逾期不返回的假造 ROI 進行有界限的程序終止（bounded process termination）。watchdog termination 屬於控制器失敗佐證，不可偽造 ROI 收據。

若未來需要非同步保留完整影格，應設計新版本，而非放寬 v1 規範。

### 16.4 RoiIngressGapV1

gap 物件包含 schema、session/source ID、閉區間遺漏範圍（inclusive missing range）、偵測 QPC、相對於 start 的 offset、reason 及 `reset_temporal_state`。僅在 gap 長度大於或等於 3 時，reset 旗標才設為 `true`。`accept_gap` 必須先於後續影格呼叫，並在 100,000,000 ns 內完成。

### 16.5 RoiAcceptResultV1

result 具備下列欄位：

| 欄位 | 條件 |
|---|---|
| `schema` | `whole-home-agent.roi-accept-result.v1` |
| `capture_session_id` | 必須與提交的 frame 一致 |
| `source_sequence` | 必須與提交的 frame 一致 |
| `status` | `ACCEPTED` 或 `REJECTED` |
| `reason_code` | accepted 時為 null，rejected 時為固定代碼 |
| `accepted_monotonic_ns` | accepted 時為 QPC，rejected 時為 null |
| `roi_ingress_version` | 必須與 open session 一致 |
| `roi_config_hash` | 必須與 open session 一致 |

rejection code 僅限：`ROI_REJECT_CAPACITY`、`ROI_REJECT_UNAVAILABLE`、`ROI_REJECT_INTERNAL`。只要發生第一次 reject、例外狀況或逾時，工作階段即告終止。

`ACCEPTED` 僅代表傳輸已被受理，並不代表已偵測到 ROI、辨識出物體、形成 claim 或代表任何現實事實。

---

## 17. 緩衝區所有權與反壓機制（Backpressure）

應用程式所持有的完整影格緩衝區上限總計為 5 個：

| 所有者 | 上限 | 釋放時間點 |
|---|---|---|
| CaptureHost outbound queue | 3 | 完成 record 寫入或管道故障時 |
| SemanticHost decoder | 1 | 產生 ROI lease 或驗證失敗時 |
| ROI ingress lease | 1 | ROI 呼叫 `release()` 時 |
| **總計** | **5** | **嚴禁超出** |

單一影格大小為 2,764,800 位元組，因此應用程式 payload 上限為 13,824,000 位元組。此數值不包含 Windows 驅動程式緩衝區、管道內部緩衝區、託管物件（managed object）、固定標頭或暫存轉換表面（conversion surface），該部分將另行量測。

CaptureHost 在同時間最多僅能持有一個應用程式層級可見的 `MediaFrameReference`，並在轉換完成或拒絕後立即釋放。攝影機回呼（callback）不得等待管道 I/O 或 ROI 處理，應直接複製至可用 slot 或記錄為 gap。嚴禁在每次回呼中建立無界限的 task、佇列、列表或位元組陣列。

當佇列滿載時，不得以新影格覆寫已排入佇列的舊影格，應將新的 position 記錄為 `queue_overflow`。gap metadata 不佔用原始影格的 slot。

---

## 18. 狀態轉移

CaptureHost 依序進行下列狀態轉移：

```text
CREATED
  -> PIPE_CONNECTING
  -> PIPE_READY
  -> CAMERA_OPENING
  -> READER_READY
  -> STREAMING
  -> FINISHING
  -> SEALED
  -> CLOSING
  -> CLOSED
```

遇到 Cancel 操作時，轉移路徑為 `STREAMING -> ABORTING -> ABORTED -> CLOSING`；發生異常時，則從任何非終止狀態（non-terminal state）轉移為 `FAILED -> CLOSING`。終止狀態後嚴禁重新啟動處理。

進入 `FINISHING` 後，立即停止產生新的 position，並依序停止並銷毀 reader 與攝影機；其後發送已轉換完畢的 pending frame/gap，唯有在確認資源成功釋放後，才發送 SEALED end。不得因管道排空（flush）而延長佔用攝影機的時間。若釋放攝影機失敗，在可行的情況下應發送 `FAILED/CAPTURE_RESOURCE_RELEASE_FAILED`。

SemanticHost decoder 依序進行下列狀態轉移：

```text
LISTENING
  -> WAIT_START
  -> OPENING_ROI
  -> ACTIVE
  -> VERIFYING
  -> COMPLETE
  -> CLOSED
```

一旦發生協定、管道、ROI、逾時、digest 或資源異常，立即轉移至 `FAILED` 狀態，後續不再向 ROI 傳送任何影格，僅執行具界限的清理動作（bounded cleanup）。對於第二次 start、第二個用戶端連線、end 之後的訊息、end 之前的 EOF 或無法解釋的序號遺漏，一律予以拒絕。

---

## 19. 逾時與操作限制

| 處理階段 | 上限 | 逾時動作 |
|---|---|---|
| 管道連線與相互身分驗證 | 5 秒 | 開啟攝影機前直接判定失敗 |
| 攝影機/reader 初始化 | 5 秒 | 關閉資源並判定失敗 |
| 攝影機開啟至關閉 | 37 秒 | 強制關閉，判定失敗 |
| start 後管道無進展 | 1 秒 | 工作階段失敗 |
| ROI frame accept 返回時限 | 100 ms | 判定為 `ROI_CONSUMER_TIMEOUT` |
| ROI gap accept 時限 | 100 ms | 工作階段失敗 |
| pending gap/end flush 時限 | 2 秒 | 不予封印（seal） |
| CaptureHost reader/camera 清理 | 2 秒 | 若尚可發送 end 則記為 `CAPTURE_RESOURCE_RELEASE_FAILED`，否則視為控制器失敗佐證 |
| SemanticHost pipe/ROI/buffer 清理 | 2 秒 | 判定為 `ROI_RESOURCE_RELEASE_FAILED` |

所有逾時均以 QPC 時間進行計算。

Finish 操作會停止產生新 position、正常釋放攝影機，並嘗試 flush 已核算的轉換訊息以完成封印。Cancel 操作則不進行封印，盡可能發送 `ABORTED`。擷取進行中若視窗被關閉，一律視為 Cancel 處理，不得視為 Finish。

---

## 20. 傳輸失敗代碼

ROI delivery receipt 僅允許下列失敗代碼：
- `ROI_SCHEMA_INVALID`
- `ROI_SESSION_MISMATCH`
- `ROI_SEQUENCE_INVALID`
- `ROI_DIMENSION_MISMATCH`
- `ROI_PIXEL_FORMAT_INVALID`
- `ROI_LAYOUT_INVALID`
- `ROI_PAYLOAD_SIZE_INVALID`
- `ROI_QUEUE_FULL`
- `ROI_CONSUMER_TIMEOUT`
- `ROI_CONSUMER_REJECTED`
- `ROI_BUFFER_LEAK`
- `ROI_DIGEST_MISMATCH`
- `ROI_PIPE_CLOSED`
- `ROI_EARLY_END`
- `ROI_RESOURCE_RELEASE_FAILED`

發生的第一個終止性失敗即作為收據的 `failure_code`。即使在清理過程中發生額外失敗，亦不得覆寫最初的失敗原因，而應透過 `resource_release_ok=false` 表達。嚴禁將例外型別、堆疊追蹤（stack trace）、裝置名稱、管道名稱或影格內容寫入公開收據中。

若在發送 start 之前，對等身分、DACL、攝影機權限、裝置註冊、格式或初始化階段即已失敗，由於此時 ROI 工作階段根本尚未建立，嚴禁偽造 ROI 收據。信任控制器應另行記錄乾淨且無敏感資訊的啟動失敗記錄（sanitized launch failure）。

攝影機格式相關的啟動失敗代碼僅限下列項目：
- `LAUNCH_CAMERA_EXCLUSIVE_CONTROL_UNAVAILABLE`
- `LAUNCH_CAMERA_FORMAT_NOT_FOUND`
- `LAUNCH_CAMERA_FORMAT_AMBIGUOUS`
- `LAUNCH_CAMERA_FORMAT_SET_FAILED`
- `LAUNCH_CAMERA_FORMAT_VERIFY_FAILED`

啟動記錄中不得包含裝置 ID、格式列舉列表、例外文字或影格資料。若在 start 之後格式發生變動，應套用既有的串流錯誤代碼 `CAPTURE_FORMAT_CHANGED`。

---

## 21. RoiDeliveryReceiptV1

收據必須在工作階段結束且 ROI 清理完成後建立 1 次。欄位規範如下：

| 欄位 | 條件 |
|---|---|
| `schema` | `whole-home-agent.roi-delivery-receipt.v1` |
| `capture_session_id`, `source_id` | 工作階段識別碼 |
| `capture_config_hash`, `roi_config_hash` | 已解析的設定雜湊值 |
| `roi_ingress_version` | 固定 consumer 版本 |
| `stream_sha256` | 狀態為 SEALED 時的驗證雜湊值，其餘情況為 null |
| `source_end_status` | 經過驗證的 SEALED, ABORTED, FAILED。若在 start 之後、收到合規 end 之前發生本機失敗，則為 null |
| `source_failure_code` | 經過驗證的 capture 失敗代碼。若為 SEALED 或尚未收到合規的 source end，則為 null |
| `status` | `COMPLETE`, `ABORTED`, `FAILED` |
| `first_source_sequence`, `last_source_sequence` | 非空時分別為 0 與最後數值；為空時兩者皆為 null |
| `acquisition_positions` | 已核算的 position 總數 |
| `frame_messages_received` | 經過驗證的 frame 總數 |
| `roi_frames_accepted` | 已 accepted 且釋放完畢的 frame 總數 |
| `gap_positions` | gap position 總數 |
| `roi_frames_rejected` | 合法 reject 總數 |
| `capture_overrun_positions` | 對應的 gap 數量 |
| `queue_overflow_positions` | 對應的 gap 數量 |
| `source_unavailable_positions` | 對應的 gap 數量 |
| `delivery_latency_p50_ns` | 可用時取 nearest-rank p50 |
| `delivery_latency_p95_ns` | 可用時取 nearest-rank p95 |
| `delivery_latency_max_ns` | 可用時的最大值 |
| `peak_application_frame_slots` | 0 至 5 |
| `clock_basis_verified` | 跨程序 QPC 驗證結果 |
| `resource_release_ok` | 所有資源具界限釋放（bounded release）的結果 |
| `failure_code` | 若為本機傳輸失敗則為固定代碼。其餘情況（包含 COMPLETE、僅 source 端發生的 ABORTED 或 FAILED）皆為 null |
| `raw_retention` | `none` |

計數值必須滿足下列等式：
```text
acquisition_positions = 0                        # 空工作階段時
acquisition_positions = last_source_sequence + 1  # 非空工作階段時
gap_positions = Σ(last_missing - first_missing + 1)
acquisition_positions = frame_messages_received + gap_positions
gap_positions = capture_overrun_positions
              + queue_overflow_positions
              + source_unavailable_positions
```

延遲時間計算公式為 `accepted_monotonic_ns - captured_monotonic_ns`，負值一律拒絕。數值採遞增排序，索引值以 $\lceil p \times n \rceil - 1$ 的 nearest-rank 方式計算。若 accepted frame 為 0，則延遲欄位皆為 null。

唯有在完全符合下列條件時，才允許將狀態標記為 `COMPLETE`：
1. start/frame/gap/end 的順序與所有欄位皆完全合法。
2. source end 為 SEALED 且 source failure 為 null。
3. stream digest 比對完全一致。
4. 所有 position 均透過 frame 或 gap 確實核算 1 次。
5. 所有接收到的 frame 均在 ROI 端獲得 accepted，且 reject 數為 0。
6. 所有 lease 均確實釋放 1 次。
7. 未發生逾時、管道中斷、第二個用戶端連線或未處理的例外。
8. `resource_release_ok=true`。
9. 未將 raw bytes 寫入檔案、記錄、例外、SQLite、presenter 或模型中。
10. 收據本身通過精確欄位驗證（exact-field validation）。

狀態判定優先順序為：若本機發生異常則為 `FAILED`；其次若 source 端為 `FAILED` 則為 `FAILED`；source 端為 `ABORTED` 則為 `ABORTED`；唯有在 source 端為 `SEALED` 且所有條件皆滿足時才為 `COMPLETE`。若在 start 之後、收到合規 end 之前發生本機失敗，設定為 `source_end_status=null`、`source_failure_code=null`，嚴禁憑空捏造不存在的 source end。

---

## 22. 記錄、保留與隱私規範

結構化記錄中僅允許包含：元件/組建版本、過濾後的 profile/config hash、opaque session ID、狀態轉移、frame/gap/reject 計數、佇列深度、彙總時間數據、固定 failure code、時鐘基準、資源釋放狀況及最終狀態。

嚴禁在記錄、收據、檔案、SQLite 或模型 context 中包含下列項目：
- raw RGB bytes、base64、縮圖、裁切影像、像素取樣資料
- 單一影格雜湊值（per-frame hash）
- 攝影機硬體 ID 或裝置名稱
- 套件權杖、管道 nonce、管道完整名稱
- 人名、房間名稱、地址、完整提問（full query）
- 憑證（credential）、同意書全文、授權書全文
- 提供者/模型之傳輸內容（payload）
- 包含影格資料的例外訊息文字

原始影格皆為暫時性資料（transient）。歸還至緩衝集區（buffer pool）前可採取 best-effort 覆寫清除，但不可宣稱已保證清除 Windows、驅動程式或受控執行環境內部所有的暫存複本。

---

## 23. 開發隔離

開發面向劃分如下：

| 開發介面 | 允許項目 | 禁止項目 |
|---|---|---|
| 現有 Python 基底/展示 | B0/B1、固定影片、UI | 攝影機依賴項目、裝置列舉、live 路由 |
| `stream_sim_d0` | 純契約、驗證器、生成影格 | Windows 攝影機 API、隱私資料、網路連線 |
| CaptureHost 套件 | 攝影機、RGB 轉換、管道寫入端、可見介面控制項 | ROI、偵測器、帳本、SQLite、LLM、網路、音訊 |
| SemanticHost 套件 | 管道讀取端、ROI ingress、固定 Python | webcam/mic/網路能力、攝影機 API、D1 儲存 |
| 硬體測試環境（hardware test lane） | 精確簽署的套件、已註冊測試攝影機 | 無人值守 CI、家庭環境、人像、雲端、可重複使用之憑證 |

Windows 專案僅能在明確指定的 Windows 建置目標下進行還原與建置。一般的 `uv run`、`help`、`import`、可編輯安裝（editable install）、macOS/Linux 測試或 Streamlit 啟動過程，絕對不可呼叫 Windows 套件或攝影機後端。

必須透過黑箱測試（black-box test）驗證 AppContainer、manifest、DACL、拒絕網路存取、拒絕檔案系統存取、非預期子程序以及攝影機權限配置。不可僅憑 manifest 存在設定即視為已達成隔離證明。

---

## 24. 實作階段

### R0 文件確認
審查本文件，確認 ROI 意指入口邊界，並確認各項固定參數、wire、lease、逾時、收據及完成條件。此階段不新增程式碼、套件依賴、安裝套件或裝置權限。

### R1 純 Python 生成契約
實作不可變型別（immutable value）、嚴格驗證器、canonical JSON、wire 編解碼器、digest、收據計算器、生成測試 producer 及假造 ROI（fake ROI）。不導入 Windows API 或攝影機依賴。

- **正常情境測試應涵蓋**：空白 seal、單一 frame、300 個 frame、1 至 2 個 gap、3 個以上 gap 的重設機制、提早 Finish、雙向來回處理（round-trip）。
- **異常情境測試應涵蓋**：欄位缺失/冗餘、型別錯誤、錯誤的 magic/version/flag/length、不合法的 UTF-8、重複的 JSON key、未發送 start 先送 frame、重複發送 start/end、end 之後傳送訊息、序號遺漏/逆轉/重複、時間戳記倒退、數值溢位、尺寸/layout 不符、不合法的 gap、digest 損毀、ROI 拒絕/例外/逾時、未釋放或重複 release lease、管道分段讀取、第 6 個 frame slot、取消操作以及清理失敗處理。

R1 完成時，仍不開放使用實體攝影機。

### R2 Windows 生成影格之跨套件測試
首先執行 **R2A**：使用最小二進位檔驗證兩個各自獨立的 non-full-trust AppContainer 之間，是否能確實建立並使用具名管道。由於 Microsoft 的一般 IPC 文件與 `ConnectNamedPipe` API 文件之間的規範敘述存在出入，嚴禁採用合併為單一套件或使用 `runFullTrust` 方式規避限制。若 R2A 驗證失敗，必須退回 DECIDE 階段重新選定本機 IPC 機制。

唯有在 R2A 通過後，才建置獨立 AppContainer 的 CaptureHost 與 SemanticHost，並以 R1 的生成向量取代攝影機 API 進行傳輸。驗證項目包含：套件身分、manifest、DACL、錯誤 SID、第二個用戶端連線、分段 I/O、反壓機制、Python/C# 位元組一致性、QPC 一致性、程序終止、拒絕網路與檔案系統存取。

必須確認攝影機權限提示出現次數為 0，且裝置列舉次數為 0。

### R3 容錯與隔離測試
注入各項異常情境：佇列滿載、慢速 ROI、管道斷線、格式錯誤的 metadata、超大資料、digest 損毀、錯誤套件、重複啟動、於各狀態下取消操作、程序當機。確認所有情境皆能維持 fail-closed，且不殘留任何原始資料、fallback 來源、full-trust 路由或網路傳輸路徑。

### R4 經特別許可的實體機驗收
R4 目前不執行。實施前必須完成政策採納、角色分配、攝影機與非家庭視野登記、取得必要同意書、固定套件與設定 hash，並取得具備執行期限的啟動決策（activation decision）。

在進行正式執行（positive run）前，必須先驗證：權限遭拒、裝置不存在/錯誤、不支援的格式、第二個用戶端連線、Cancel、Finish、管道斷線與程序當機等情境。其後，在不包含人物或私人空間的生成校正標靶前，由人員操作進行 1 次最長 30 秒的實機執行。

---

## 25. R4 驗收標準

未來的實機正式執行，必須在完全符合下列所有指標時方可判定為合格：

| 指標 | 合格條件 |
|---|---|
| `acquisition positions` | 300 |
| 發送之影格全數獲 ROI accepted/released | 100% 全部影格 |
| `ROI rejected` 數 | 0 |
| `capture overrun gap` 數 | 0 |
| `queue overflow gap` 數 | 0 |
| `source unavailable gap` 數 | 0 |
| p95 capture-to-accept 延遲 | 100,000,000 ns 以下 |
| max capture-to-accept 延遲 | 300,000,000 ns 以下 |
| 應用程式原始影格 slot 峰值 | 5 以下 |
| 攝影機從開啟到關閉時間 | 37,000,000,000 ns 以下 |
| 原始檔案/記錄/SQLite 寫入次數 | 0 |
| 網路連線/傳送位元組 | 0 |
| `clock basis verified` | `true` |
| `resource release` | `true` |
| `receipt status` | `COMPLETE` |

此合格判定僅代表在指定 Windows 組建、套件、攝影機、驅動程式、設定檔、生成場景與啟用條件下，達成 capture-to-ROI 的傳輸成果。不代表 ROI 精度、物體辨識能力、家庭實用性或 24 小時連續運轉能力。

---

## 26. 測試向量（Test Vector）

在 R1 階段必須固定一組生成 fixture package，包含下列項目：
- 載明 fixture ID、schema 版本、產生器版本、來源/授權、內容 hash 及預期用途的 manifest
- 各訊息種類的標準 metadata 位元組
- 非照片的決定性（deterministic）RGB 樣式
- 預期的 16 位元組前綴
- 完整的 wire record
- digest 原像（preimage）與 SHA-256
- ROI session/frame/gap/result/receipt 的 canonical JSON
- 變更 1 個位元組或 1 個欄位時預期的失敗結果

RGB 樣式應包含黑、白、紅、綠、藍、水平/垂直漸層（ramp）、不對稱角落標記與邊界座標，藉此驗證通道對調、stride、旋轉、鏡像及差一錯誤（off-by-one）。嚴禁僅因 golden file 測試未過而自動重新產生測試資料。

---

## 27. 交付予 ROI 負責團隊之成果物

擷取模組負責人員應交付下列成品予 ROI 負責團隊：
1. 本整合規格書
2. ROI session/frame/gap/end/result 的不可變公開型別（immutable public type）
3. 嚴格驗證器
4. 同步 ROI 介面
5. 生成輸入資料與合規測試向量
6. lease 濫用測試案例
7. 收據 schema 與計算公式
8. 座標、layout 與色彩測試案例
9. 逾時、slot 上限與故障注入掛鉤（fault injection hook）

嚴禁交付攝影機代碼（handle）、管道 handle、裝置 ID、私有影格資料集、憑證、帳本、資料庫、LLM/模型介面或動作執行介面。

---

## 28. 負責作業之完成條件

在目前權限範圍下，滿足 R0 至 R3 的下列條件時，即可視為已完成負責作業：
1. 已確認本文件對 ROI 入口的解讀定義。
2. 通過 R1 所有正常與異常情境的一致性測試。
3. 在不使用攝影機的情況下，通過 R2 的 Python/C# framing、套件隔離、對等端身分確認、QPC、lease 及資源清理測試。
4. 通過 R3 驗證 fail-closed 機制與資源上限控管。
5. 不影響現有 B0/B1 的測試結果。
6. 一般 Python 路徑中完全不存在攝影機的 import、套件依賴或裝置列舉程式碼。
7. 原始像素資料絕不寫入磁碟、SQLite、記錄、錯誤訊息、presenter 或模型。
8. 無法透過環境變數、提示詞、模型、一般 CLI 或 import 啟用 live source。
9. 生成的收據具可重現性，且通過精確欄位驗證。

R4 涉及額外的營運許可與實體機驗證，不列入目前的完成條件。

---

## 29. 停止條件

若發生下列任一情況，必須立即停止實作並退回架構設計決策階段：
1. ROI 被定義為裁切後的輸出影像，而非本文件所定義的入口。
2. ROI 需要非同步保留完整影格。
3. 在未進行縮放或無驅動程式 fallback 的情況下，無法取得指定的固定解析度與週期。
4. 無法驗證套件或管道對等端的身分識別。
5. SemanticHost 被要求必須具備 webcam 或網路能力。
6. 無法在兩個 AppContainer 之間安全地使用具名管道。
7. 無法驗證跨程序的 QPC 基準。
8. 5 個 frame slot 或逾時上限無法滿足需求。
9. 為了除錯或評估目的而必須儲存原始媒體資料。
10. 人物或私人空間進入攝影機視野。
11. 提出使用非封裝（unpackaged）或 full-trust 模式存取攝影機的替代方案。
12. 在政策採納與正式啟用決策確立前，被要求執行 live 運作。

雖然可繼續進行安全的生成測試，但絕對不得私自在程式碼、設定、測試或文件中放寬任何限制。

---

## 30. 最終產出物

依據本規格書所產生的最終產出物，並非網路攝影機視訊或辨識結果，而是以下 4 項：
1. 生成輸入與未來的攝影機輸入均能轉換為同一套契約。
2. 在隔離的 Windows 程序之間，能以有限且可驗證的方式傳遞 frame、gap、start、end。
3. 能以工作階段為單位，確切核算 ROI 入口已受理並釋放各個影格。
4. 在不殘留任何原始影格的前提下，以乾淨無隱私外洩的收據（sanitized receipt）清楚說明執行成功或失敗的歷程。

唯有滿足上述條件，方能定義為「從網路攝影機到 ROI 入口的傳輸機制已開發完成」。其後的 ROI 計算、物體偵測、追蹤、claim、記憶與問答功能，均屬於其他負責團隊、個別規格書與獨立驗證的範疇。

---

## 31. 參考之 Windows 官方第一手資料

- [MediaCapture initialization](https://learn.microsoft.com/en-us/uwp/api/windows.media.capture.mediacapture.initializeasync)
- [MediaFrameReader](https://learn.microsoft.com/en-us/uwp/api/windows.media.capture.frames.mediaframereader)
- [MediaCapture sharing mode](https://learn.microsoft.com/en-us/uwp/api/windows.media.capture.mediacaptureinitializationsettings.sharingmode)
- [Camera privacy controls](https://support.microsoft.com/en-us/windows/manage-app-permissions-for-your-camera-in-windows-87ebc757-1f87-7bbf-84b5-0686afb6ca6b)
- [App capability declarations](https://learn.microsoft.com/en-us/windows/uwp/packaging/app-capability-declarations)
- [Windows application packaging and deployment](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/)
- [AppContainer isolation](https://learn.microsoft.com/en-us/windows/win32/secauthz/appcontainer-isolation)
- [Named pipes](https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipes)
- [Named-pipe security and access rights](https://learn.microsoft.com/en-us/windows/win32/ipc/named-pipe-security-and-access-rights)
- [Windows app IPC](https://learn.microsoft.com/en-us/windows/apps/develop/communication/interprocess-communication)
- [ConnectNamedPipe AppContainer restrictions](https://learn.microsoft.com/en-us/windows/win32/api/namedpipeapi/nf-namedpipeapi-connectnamedpipe)
- [Sharing named objects](https://learn.microsoft.com/en-us/windows/apps/develop/communication/sharing-named-objects)
- [QueryPerformanceCounter](https://learn.microsoft.com/en-us/windows/win32/api/profileapi/nf-profileapi-queryperformancecounter)

# B0 → B1 最小架構提案與實作對照

- **Architecture decision status:** `PROPOSED — NOT ADOPTED`
- **Bounded code status:** `IMPLEMENTED / VERIFIED ON ONE PROJECT-GENERATED SYNTHETIC REPLAY`
- **Scope:** 預錄、合法可用的 D0 影片；不含即時攝影機、家庭私有資料或行動能力
- **Runtime:** 單程序模組化單體；同步、循序、local-only
- **Operation:** `OPERATE DISABLED`
- **As of:** `2026-09-01 Asia/Taipei`

這份文件起初回答最重要的架構問題：下一層影片感知應該接在哪裡、哪些元件能改狀態，以及哪些複雜度不應加入。使用者之後明確授權了一個 bounded implementation slice，因此本文也記錄目前程式與原提案的對照。實作不會自行採用 proposed governance，也不授權攝影機、家庭資料、帳號、裝置或實體行動。

## 可視化產物

- [系統責任與信任邊界](b0-b1-system.architecture.html)（self-contained HTML）
- [預錄影片到可追溯回答的資料流](b0-b1-perception.dataflow.html)（self-contained HTML）
- [architecture JSON source](b0-b1-system.architecture.json)
- [data-flow JSON source](b0-b1-perception.dataflow.json)

HTML 可下載後直接用瀏覽器開啟，包含 guided views、搜尋、明暗主題與匯出功能。固定 viewer 介面目前沒有 `zh-TW` locale，因此圖內架構文字與 viewer 固定文字使用英文；本說明文件保留繁體中文。

## 結論

目前不需要重寫 B0，也不需要先建立 Memory Core、graph、vector store、multi-agent、queue 或 durable database。B1 已以可替換的離線感知 adapter 實作：它把一段固定、hash-pinned、專案生成的預錄影片轉成既有 `ClaimCandidate`，再交給 B0 `ClaimCommitter`。只有 B0 commit boundary 可以建立 `AcceptedClaim`；detector、tracker、relation inference、LLM/VLM 與 UI 都不能直接寫入狀態。

主路徑是：

```text
project-generated prerecorded D0 + manifest
  -> PTS decoder + motion/periodic scheduler
  -> canonical detector report
  -> clip-local tracker + binding + temporal rules
  -> canonical ClaimCandidate
  -> existing deterministic ClaimCommitter
  -> session-local AcceptedClaim ledger
  -> pure relation projection
  -> scoped AnswerTrace
```

這讓我們可以先測「影片感知是否真的改善 key／bag／sofa 故事」，又不把模型 SDK、影格、信心分數或追蹤器型別滲入 domain。

## 現況與責任

| 邊界／元件 | 狀態 | 唯一責任 | 明確禁止 |
|---|---|---|---|
| Frozen D0 fixture adapter | `B0 IMPLEMENTED` | 將封閉 JSON fixture 轉成 `ClaimCandidate` | 影片、網路、攝影機、隱藏 I/O |
| Claim commit boundary | `B0 IMPLEMENTED` | 驗證、拒絕、idempotency、identity conflict、source order、containment cycle | 猜測物理真相、接受 model SDK type |
| Session claim ledger | `B0 IMPLEMENTED` | 記錄單次 replay 中通過規則的 claims | 宣稱 world truth、跨 run 持久化 |
| Relation projection | `B0 IMPLEMENTED` | 純函式重建 `inside`／`at_zone` 與有效性 | 成為權威資料源、last-write-wins 隱藏衝突 |
| Scoped StateQuery | `B0 IMPLEMENTED` | 依 fixture、run、as-of 回傳 status 與 trace | 暴露 ledger、filesystem、model、credential 或 generic tool |
| Recorded perception adapter | `B1 IMPLEMENTED / SYNTHETIC-ONLY VERIFIED` | 將固定 project-generated D0 轉成 canonical candidates | live camera、RTSP、cloud、claim commit、raw-frame persistence |
| CLI／Streamlit presentation | `B1 IMPLEMENTED / CLOSED DEMO` | 呈現固定 replay 的 `AnswerTrace`、證據、abstention、metrics 與 receipt | 任意 upload/path、camera、chat、寫 claims、授權 operation、privileged handle |
| Action plane | `ABSENT / DISABLED` | 無 | 所有外部、帳號、裝置與實體作用 |

`IMPLEMENTED` 只表示程式中存在；B0 測試證據也只涵蓋指定 fixture 與語意，不證明 CV、真實家庭、效能或物理事件。

## 最小合約

B1 對 application 暴露一個重要、會變動的邊界：循序提供 canonical `ClaimCandidate` 的 `ClaimCandidateSource` port。`RecordedPerceptionSource` 與 contract tests 已凍結下列語意：

- composition root 選擇 fixture source 或 recorded-perception source；
- source 只產生 `ClaimCandidate`，application 不接收 OpenCV frame、tensor、YOLO result 或 tracker object；
- 每個 candidate 保留 fixture/source identity、sequence/offset、timestamp basis、artifact/config version 與 epistemic status；
- source 順序是確定且可 replay 的；資源由 composition root 明確關閉；
- 每個 candidate 仍逐一通過同一個 `ClaimCommitter`；不得另建 B1 快速寫入路徑。

Detector、tracker 與 event extractor 可以先留在同一個 adapter package 內。只有當它們需要獨立替換、測量或有第二個實作時，才增加更窄的內部 port；不為每個 class 建 interface。

## 五個必須分離的面

| 面 | 本階段內容 | 權威與信任語意 |
|---|---|---|
| Data | 預錄影格、boxes、tracks、event hypothesis、claims、derived projection | 來源與模型輸出都是 data；不得自行變成 authority |
| Control | 已驗證的 config、model/dataset manifests、hashes、thresholds、zones、rule version | 決定如何運算，不代表同意或家庭政策 |
| Authority | proposed governance、scope-authorized current direction、未來 consent/policy checkpoint | 只能由正確角色明確授予；模型與文件不能自授權 |
| Action | 本階段不存在 executor 或 `ActionIntent` | 預設拒絕；計算 request 不是 action intent |
| Physical outcome | 本階段不可達 | 未來 command acknowledgement 也不等於獨立觀察到的結果 |

## 認知與證據語意

感知鏈上的每一層必須保留自己真正知道的內容：

1. YOLO box 是 model report，不是物件存在的權威事實。
2. tracker identity 是跨影格關聯假說，不是持久的人或物件身分。
3. event extractor 產生 `move_to`、`put_into`、`take_out` 等候選；不直接 commit。
4. `AcceptedClaim` 只表示 candidate 通過 schema 與 invariant。
5. projection 是可重建的 current estimate。
6. `key -> bag -> sofa` 可回答為 derived／estimated location；若只有 bag 被觀察移動，不得寫成「觀察到 key 自己移動」。
7. 遮擋、過期、absent、unknown 與 conflict 不可互換；證據不足時 abstain。

## 失敗語意

- 影片 decode、detector 或 tracker 失敗：輸出 typed failure／abstention，不製造 observed event。
- candidate schema 錯誤、次序錯誤或 cycle：commit 原子拒絕，ledger 與 projection 不變。
- 同一 claim identity、相同 payload：idempotent；同 identity、不同 payload：explicit conflict。
- 不完整 replay：不得呈現為 passed 或 current；B1 restart 從固定來源與 resolved config 重新 replay。
- config、model 或 dataset hash 缺失：啟動失敗，不退回 mutable `latest`。
- evidence conflict 或 staleness：回答 `CONFLICT`／`UNKNOWN`，不以較新模型輸出靜默覆寫歷史。

## 可驗證品質情境

| ID | Stimulus | 預期行為 | 需要的證據 |
|---|---|---|---|
| `B1-S1` | 固定 indoor D0 出現 move／containment 故事 | 產生 canonical candidate，經 B0 得到 scoped answer 與 trace | frozen event labels、event F1、answer correctness |
| `B1-S2` | adapter 送出 malformed／hostile candidate | 原子拒絕且不改 ledger／projection | contract + hostile regression tests |
| `B1-S3` | key 被遮擋，只觀察 bag 移到 sofa | key location 標記 estimated；不虛構 observed key move | golden replay + epistemic assertions |
| `B1-S4` | detector／tracker 中途失敗 | typed failure 或 abstain；B0 deterministic suite 不受影響 | failure injection tests |
| `B1-S5` | 相同 source/config/hash 重跑 | 相同 candidate ordering 與答案；無外部副作用 | paired replay manifest and hashes |
| `B1-S6` | 替換 detector 或 tracker | 只改 adapter/config；domain contracts 與 B0 tests 不變 | adapter contract tests + full B0 suite |
| `B1-S7` | 在指定 GPU 跑固定影片 | 同時報品質與成本，不只挑最好結果 | p50/p95 latency、RTF/FPS、dropped frames、VRAM |
| `B1-S8` | 嘗試給 live/RTSP/network/device source | composition 無此 capability，啟動／測試 fail closed | import/wiring/negative capability tests |

## B1 評估 gate

進入任何「real-time」、「lightweight」、「24/7」或「improved」宣稱前，至少要有：

- 依法可使用且 manifest 固定的 indoor replay set；
- 依來源影片、場景、攝影機、人物或時間切分，避免相鄰影格洩漏；
- frozen golden/test set，禁止用 test 調 threshold、tiling 或 prompts；
- 同一資料、硬體、輸入、warm-up 與測量方法的 paired comparison；
- event-level precision／recall／F1、scoped answer correctness、conflict／unknown／abstain correctness；
- p50/p95 latency、RTF 或 FPS、dropped frames、peak VRAM；
- resolved config、code revision/dirty flag、seed、artifact/dataset/config/lock hashes 與 runtime/GPU versions。

NTU aerial small-object 作業可以做方法預篩，但不能直接支持「家中小物件改善」；候選方法還要通過 frozen indoor set。

## 延後複雜度的觸發條件

| 候選複雜度 | 現在 | 只有在以下證據出現時再考慮 |
|---|---|---|
| Durable database | 不加入 | 已採用跨 run 查詢、retention、migration、correction/retraction 需求 |
| Graph database／Memory Core | 不加入 | typed relation projection 無法回答已凍結的必要查詢，且 benchmark 顯示替換收益 |
| Queue／background worker | 不加入 | 循序 replay 未達已定義 throughput，且 overload/backpressure 語意已先決定 |
| Multi-agent runtime | 不加入 | 出現真正獨立的責任域、權限與可驗證協調需求，單 orchestrator 無法安全表達 |
| VLM／LLM in perception | 不加入 | detector/tracker baseline 在 frozen indoor gate 被證偽，且 privacy/cost/latency gate 可接受 |
| Live camera／RTSP | 禁止 | `ACTION_POLICY.md` 採用、角色/consent/retention/enforcement 完成，且另有 activation decision |

## 實作進度

1. **B1-0 — contract seam：完成。** 最窄 candidate-source port、fake source、typed run receipt 與 partial-failure tests 已存在；B0 golden hash 未改變。
2. **B1-1 — recorded source：完成於一段 synthetic D0。** Allowlisted local reader、manifest/hash/license validation、PTS decode 與 motion-plus-periodic schedule 已存在；raw frames 不持久化。
3. **B1-2 — baseline perception：完成 synthetic smoke 與 bounded public detector screen。** RGB detector、clip-local IoU tracker、binding 與 conservative relation rules 已接通；VISOR paired baseline 選出 full-frame RetinaNet-FPN 候選，RF-DETR Nano 仍只有 hash-pinned SDK translation seam。
4. **B1-3 — evaluation and presentation：完成固定 synthetic envelope 與兩個分離的 public screens。** AP/recall/tracking/event/answer/latency/FPS/dropped-frame/VRAM evaluation 與 closed CLI/Streamlit demo 已存在；VISOR 只做 sparse detector evaluation，VOST 只做 consecutive scheduler/cost evaluation。兩者都不會進入 claim commit path，因此仍沒有 fixed-camera、real-home 或 object-movement product claim。

任何步驟若需要 live/private sensing、cloud egress、credential、account/device mutation 或 physical action，必須停止並走 `ACTION_POLICY.md` 的角色、同意、風險與 activation gate。

## 架構交付證據

兩張圖由 Archify `v2.16.0` 產生；工具本身沒有作為 runtime dependency 加入專案。系統圖的 17 個 source references 固定到 public implementation revision `5b9a72663dbcc7a8c519d928e6581ecbbbf1f53f`。

| Diagram | Specification SHA-256 | HTML SHA-256 | Automated gate | Perceptual review |
|---|---|---|---|---|
| Architecture | `a806baedc33416742410c7e4557645551f8999cfca3ef9ae8d5fd3cfe8b21e72` | `114cfbac646ae5a4a3c8e7fcad6abefd2b297f709e072289b82b7bbb7ba1bb22` | 9/9 showcase, 0 errors, 0 warnings; four desktop containment/readability checks passed | inspected light/dark at 1440×900 and 2048×1320 |
| Data flow | `d16185db78379b27e5dafac6b07994796caa457df4c087b9e9eccacdba57c16f` | `202763ffff53bb95ec2c6ab6b83056027f6bdaa0cf120d255023617fbec02a92` | 9/9 showcase, 0 errors, 0 warnings; four desktop containment/readability checks passed | inspected light/dark at 1440×900 and 2048×1320 |

這些 source references 固定在 M5 implementation revision；M6 只把公開素材版本化為瀏覽器相容的 H.264 revision 2，並補上 wheel 安裝與發布驗證，沒有改變圖中責任／信任邊界。圖表證據只驗證 spec bytes、歷史 source references、rendered artifact 與指定視覺交付 envelope；它們不採用 proposed governance，也不證明真實室內準確率、runtime authority 或系統能理解真實家庭。

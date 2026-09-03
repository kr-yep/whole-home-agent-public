"""Streamlit demo for explicit local D0 persistence and bounded free-text queries."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from whole_home_agent.adapters.loopback_llm import (
    translator_from_environment,
    verbalizer_from_environment,
)
from whole_home_agent.adapters.sqlite_archive import SQLiteReplayArchive
from whole_home_agent.errors import B0Error
from whole_home_agent.memory_query import answer_question, list_known_entities
from whole_home_agent.public_demo import run_public_demo


DEMO_DATABASE = Path(".whole-home-agent/demo-memory.sqlite3")

# Display-only labels. The askable vocabulary always comes from the stored replay.
_ENTITY_LABELS = {"key": "🔑 鑰匙", "bag": "👜 包包", "sofa": "🛋 沙發"}
_ENTITY_WORDS = {"key": "鑰匙", "bag": "包包", "sofa": "沙發"}
_PREDICATE_WORDS = {"inside": "在…裡面", "at_zone": "位於"}


def _label(entity_id: str) -> str:
    return _ENTITY_LABELS.get(entity_id, entity_id)


def _word(entity_id: str) -> str:
    return _ENTITY_WORDS.get(entity_id, entity_id)


def _build_memory() -> None:
    try:
        result = run_public_demo(
            replay_run_id="public-b1-memory-ui-001",
            include_frames=False,
            archive=SQLiteReplayArchive(DEMO_DATABASE),
        )
        st.session_state["build_status"] = result["archive"]["status"]
    except B0Error as error:
        st.session_state["build_status"] = None
        st.error(f"無法建立示範記憶：{error}")


def _render_memory(memory: dict) -> None:
    """What was read out of the archive, and whether it verified."""

    left, right = st.columns(2)
    left.markdown(
        f"**來源**　`{memory['source_id']}@{memory['source_revision']}`　"
        f"`{memory['use_class']}`\n\n"
        f"**重播**　`{memory['replay_run_id']}`"
    )
    right.markdown(
        f"**內容雜湊**　`{memory['content_hash'][:16]}…` ✓\n\n"
        f"**語意雜湊**　`{memory['semantic_output_hash'][:16]}…` ✓"
    )
    st.caption(
        f"還原了 {memory['restored_claim_count']} 筆已接受的主張，"
        f"投影游標停在第 {memory['projection_frontier']} 筆。"
        f"兩個雜湊都在重建投影之前驗過，對不上就不會有答案。"
    )


def _render_tree(projection: dict, used_claim_ids: set[str]) -> None:
    """Draw the containment tree, marking the edges this answer walked."""

    edges = projection["edges"]
    if not edges:
        st.caption("這段記憶裡還沒有任何關係。")
        return
    parent = {edge["subject_id"]: edge for edge in edges}
    children: dict[str, list[dict]] = {}
    for edge in edges:
        children.setdefault(edge["object_id"], []).append(edge)
    roots = sorted({edge["object_id"] for edge in edges} - set(parent))

    lines: list[str] = []

    def walk(node: str, depth: int) -> None:
        for edge in sorted(children.get(node, []), key=lambda e: e["subject_id"]):
            used = edge["source_claim_id"] in used_claim_ids
            mark = "**" if used else ""
            indent = "&nbsp;" * (depth * 6)
            relation = _PREDICATE_WORDS.get(edge["predicate"], edge["predicate"])
            lines.append(
                f"{indent}└─ *{relation}* ─ {mark}{_label(edge['subject_id'])}{mark}"
                f"　`{edge['source_claim_id']}` · 第 {edge['source_sequence']} 筆"
                + ("　←　這次走過" if used else "")
            )
            walk(edge["subject_id"], depth + 1)

    for root in roots:
        lines.append(f"{_label(root)}")
        walk(root, 1)
    st.markdown("<br>".join(lines), unsafe_allow_html=True)
    st.caption(f"樹上共 {projection['edge_count']} 條邊；粗體是回答這一題時走過的。")


def _render_answer(result: dict) -> None:
    answer = result.get("answer")
    spoken = result["spoken"]
    st.success(spoken["text"])
    settled = result.get("contents") or result.get("verification") or result.get("presentation")
    if spoken["speaker"] != "deterministic":
        st.caption(f"由 `{spoken['speaker']}` 講述　·　結構化結果：{settled['text']}")
    elif spoken["fallback_used"]:
        st.caption("模型沒有回應，這句是本機決定性模板產生的。")

    interpretation = result.get("interpretation")
    if interpretation is not None:
        # Only shown when a model chose the query: a mis-reading belongs next to
        # the answer, not buried in an id the reader never sees.
        quoted = interpretation.get("matched_text")
        resolved = "、".join(
            f"{_label(value)}" for value in interpretation["resolved"].values()
        )
        st.info(
            f"這句沒有比對到內建的問法，所以由 `{interpretation['translator_id']}` 判讀："
            f"把「{quoted}」理解成 **{resolved}**，查詢方式 `{interpretation['operation']}`。"
        )

    st.markdown("#### 它根據什麼這樣說")
    _render_memory(result["memory"])
    st.markdown("**記憶裡的樹**")
    used = set()
    if answer:
        used = {step["source_claim_id"] for step in answer.get("relation_path") or []}
    elif result.get("contents"):
        used = {
            edge["source_claim_id"]
            for edge in result["projection"]["edges"]
            if edge["object_id"] == result["contents"]["container_id"]
        }
    _render_tree(result["projection"], used)

    if answer is not None:
        st.caption(
            f"subject={answer['subject_id']} · status={answer['status']} · "
            f"{answer['epistemic_status']}"
        )
    with st.expander("原始結構化結果"):
        st.json(result)


def _render_rejection(error: B0Error, entity_ids: tuple[str, ...]) -> None:
    """Say which rule was hit and what to try, not just the error code."""

    st.warning(f"這句我沒辦法回答：{error}")
    details = getattr(error, "details", None) or {}
    matched = details.get("matched_entity_count")
    if matched is not None and matched > 1:
        st.info("一次只能問一個東西。")
    elif matched == 0:
        st.info(
            "這句話裡沒有我認得的東西。目前只有："
            + "、".join(_word(item) for item in entity_ids)
        )
    else:
        st.info(
            "我只回答東西的位置。三種問法都可以：「鑰匙在哪」、"
            "「鑰匙在沙發上嗎」、「包包裡有什麼」。不能操作任何裝置。"
        )


def main() -> None:
    st.set_page_config(page_title="Whole Home Agent — Local Memory", page_icon="🏠")
    st.title("Whole Home Agent · Local Memory")
    st.caption("這段八秒合成重播的持久記憶 · 回答是估計值，不是真實住家")
    st.error(
        "OPERATE DISABLED · 僅存入內附的合成重播；無攝影機、上傳、雲端、住家資料或裝置動作"
    )

    if not DEMO_DATABASE.is_file():
        st.write("這個示範還沒有記憶。先把內附的八秒合成影片結果寫入本機 SQLite。")
        if st.button("建立示範記憶", type="primary"):
            _build_memory()
            st.rerun()
        return

    if st.session_state.pop("build_status", None):
        st.toast("記憶已更新")

    archive = SQLiteReplayArchive(DEMO_DATABASE)
    try:
        entity_ids = list_known_entities(archive)
    except B0Error as error:
        st.error(f"無法讀取記憶：{error}")
        return

    st.write("**我現在認得這些東西**，點一下就問：")
    for column, entity_id in zip(st.columns(len(entity_ids)), entity_ids):
        if column.button(_label(entity_id), key=f"chip-{entity_id}", use_container_width=True):
            st.session_state["question"] = f"{_word(entity_id)}在哪裡？"
            st.session_state["auto_ask"] = True
            st.rerun()

    st.text_input(
        "或自己打一句",
        key="question",
        placeholder="鑰匙在哪裡？　也可以問「鑰匙在沙發上嗎」「包包裡有什麼」",
    )
    asked = st.button("詢問記憶", type="primary") or st.session_state.pop("auto_ask", False)

    if asked:
        question = st.session_state.get("question", "")
        try:
            _render_answer(
                answer_question(
                    archive,
                    question,
                    verbalizer=verbalizer_from_environment(),
                    translator=translator_from_environment(),
                )
            )
        except B0Error as error:
            _render_rejection(error, entity_ids)

    with st.expander("重建示範記憶"):
        st.caption("重跑內附影片並覆寫本機 SQLite。內容相同時為 UNCHANGED。")
        if st.button("重建"):
            _build_memory()
            st.rerun()

    if verbalizer_from_environment() is None:
        st.caption(
            "目前由本機決定性模板回答，不需要模型。設定 WHA_LLM_ENDPOINT 與 "
            "WHA_LLM_MODEL 之後改由私有端點上的模型講述；它只重寫措辭，"
            "事實、樹的走訪與棄權都在呼叫它之前就決定了。"
        )
    else:
        st.caption(
            "回答的措辭由私有端點上的模型產生。事實、樹的走訪與棄權都在呼叫它之前"
            "就決定了；模型看不到資料庫、問題以外的內容或任何憑證。"
        )


if __name__ == "__main__":
    main()
